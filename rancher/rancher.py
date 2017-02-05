import websocket
import base64
import io
import os
import sys
import pty
import tty
import threading
import logging
import termios
import fcntl
import time
import gdapi
import tornado
import subprocess
from butterfly import utils, __version__

websocket.enableTrace(False)
logging.basicConfig(level=logging.ERROR)
log = logging.getLogger('butterfly')

client = gdapi.Client(url=os.environ.get('RANCHER_URL'),
                      access_key=os.environ.get('RANCHER_ACCESS_KEY'),
                      secret_key=os.environ.get('RANCHER_SECRET_KEY'))

def accessUri(container):
    if container is None:
        print("Invalid container: %s" % container)
        exit()
    command3  = ["/bin/sh", "-c", "[ -x /bin/bash ] && TERM=xterm-256color force_color_prompt=yes exec /bin/bash || TERM=xterm-256color force_color_prompt=yes exec /bin/sh"]
    access = container.execute(attachStdin=True, attachStdout=True, tty=True, command=command3)
    return "%s?token=%s" % (access.url, access.token)

def getById(containerId):
    container = client.by_id("container", containerId)
    return accessUri(container)

def getByName(containerName):
    containers = client.list("container", state="running", kind="container", name=containerName)
    try:
        container = containers[0]
    except IndexError:
        parser.error("container '%s' not found" % containerName)
    return accessUri(container)


class RancherSoc(object):
    def __init__(self, url):
        self.url = url
        self.output = None
        self.websoc = None
        self.connected = False

    def connect(self, output):
        self.output = output
        def on_close(ws):
            log.debug('connection closed')

        def on_message(ws, message):
            self.output(base64.b64decode(message))

        def on_error(ws, error):
            log.error('connection error', error)
            exit()

        def on_open(ws):
            log.debug('connection opened')
            self.connected = True

        ws = websocket.WebSocketApp(self.url,
                                  on_open = on_open,
                                  on_message = on_message,
                                  on_error = on_error,
                                  on_close = on_close)

        wst = threading.Thread(target=ws.run_forever)
        wst.daemon = True
        wst.start()
        conn_timeout = 5
        while not self.connected:
            time.sleep(1)
            conn_timeout -= 1

        if conn_timeout < 1:
            raise Exception('connection time out')
        self.websoc = ws
        return ws

    def push(self, message):
        self.websoc.send(base64.b64encode(message))


class Terminal(object):
    def __init__(self, user, path, session, socket, host, render_string, send):
        # session === containerId
        print("session: %s; path: %s, host: %s, user: %s" % (session, path, host, user))
        self.host = host
        self.containerId = session
        self.session = session
        self.send = send
        self.fd = None
        self.closed = False
        self.socket = socket
        log.info('Terminal opening with session: %s and socket %r' % (self.session, self.socket))
        self.path = path
        self.user = user if user else None
        self.caller = self.callee = None
        self.proxy = None
        self.websoc = None

        if tornado.options.options.motd != '':
            motd = (render_string(
                tornado.options.options.motd,
                butterfly=self,
                version=__version__,
                opts=tornado.options.options,
                colors=utils.ansi_colors)
                    .decode('utf-8')
                    .replace('\r', '')
                    .replace('\n', '\r\n'))
            self.send('S' + motd)

    def pty(self):
        url = getById(self.containerId)
        self.websoc = RancherSoc(url)
        self.websoc.connect(self.onOutput)

    def write(self, message):
        self.onInput(message)

    # Message to Rancher socket
    def onInput(self, message):
        payload = message[1:].decode('utf-8', 'replace')

        # resize
        if message[0] == 'R':
            cols, rows = map(int, payload.split(','))
            log.debug('SIZE (%d, %d)' % (cols, rows))

        # string
        elif message[0] == 'S':
            log.debug('BUTTERFLY>%r' % payload)
            self.websoc.push(payload)

        # unhandled input
        else:
            log.error('UNHANDLED>%r' % payload)
            self.websoc.push(payload)

    # Message/response from Rancher to butterfly
    def onOutput(self, message):
        payload = message.decode('utf-8', 'replace')

        log.debug('RANCHER>%r' % payload)
        self.send('S' + payload)

    def close(self):
        log.debug('CLOSING')


class RancherTty(object):
    def __init__(self, websoc):
        self.websoc = websoc
        self.payload = ''
        self.closed = False
        self.connected = False

    def pty(self):
        fd = sys.stdin
        old_settings = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        new[3] &= ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSADRAIN, new)
        tty.setraw(sys.stdin.fileno())
        tty.setcbreak(sys.stdin.fileno())
        # fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)
        cols = 250
        rows = 100
        self.onInput("stty cols %d rows %d\r" % (cols, rows))
        try:
            self.payload = ''
            exit_on = ('spam', 'quit', "exit")
            while True:
                if not sys.stdin.isatty() or not sys.stdout.isatty():
                    break

                try:
                    payload = os.read(sys.stdin.fileno(), 4096)
                    # payload = sys.stdin.read(1)
                except IOError:
                    log.error('READ ERROR')
                    payload = ''

                if payload == b'\x1b': # x1b is ESC
                    break
                if payload == b'\r' and self.payload in exit_on:
                    break

                self.onInput(payload)
                self.payload += payload.decode("utf-8")

                if self.payload.endswith("\r"): # clean payload buffer
                    self.payload = ''
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    # STDIN Message to Rancher socket
    def onInput(self, message):
        if message and len(message) != 0:
            log.debug('STDIN>%r' % message)
            self.websoc.push(message)

    # STDOUT Message/response from Rancher to butterfly
    def onOutput(self, message):
        if not sys.stdout.isatty():
            exit(0)
        # payload = message.decode('utf-8', 'replace')
        log.debug('STDOUT<%r' % message)
        os.write(sys.stdout.fileno(), message)

    def close(self):
        log.debug('CLOSING')



class ButterflyHandler(object):
    def __init__(self, host="localhost", port=57575):
        self.port = port
        self.host = host
        self.pidfile = None

    def check_pid(self, pid):
        """ Check For the existence of a unix pid. """
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        else:
            return True

    def startProcess(self, name, path):
        # Check if the process is already running
        # status, pid = processStatus(name)
        self.pidfile = '/tmp/' + name + '.pid'
        try:
            pf = file(self.pidfile,'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None

        if pid and self.check_pid(pid):
            log.info('%s already runnung' % name)
            return pid

        log.debug("%s - starting process" % name)
        # Start process
        pid = subprocess.Popen([path, '--unsecure']).pid
        # Write PID file
        pf = open(self.pidfile, 'w')
        pf.write("%s\n" % pid)
        pf.close()
        return pid

    def connect(self, containerId):
        import webbrowser
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 'butterfly.server.py')
        self.startProcess('butterfly.server.py', path)
        webbrowser.open('http://localhost:57575/session/%s' % containerId)

    def close(self):
        log.debug('CLOSING')


class TtyHandler(object):
    def connect(self, containerId):
        url = getById(containerId)
        websoc = RancherSoc(url)
        rancherTty = RancherTty(websoc)
        websoc.connect(rancherTty.onOutput)
        log.debug('STARTING')
        rancherTty.pty()

    def close(self):
        log.debug('CLOSING')
