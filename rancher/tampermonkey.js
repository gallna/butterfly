// ==UserScript==
// @name         Butterfly Terminal iframe/window
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  Replaces original rancher-server terminal with Butterfly one
// @author       TJ
// @match        *://rancher*
// @grant        none
// @require      https://cdnjs.cloudflare.com/ajax/libs/jquery.colorbox/1.6.4/jquery.colorbox-min.js
// ==/UserScript==

(function() {
    'use strict';

    function Container(button) {
        var container = {
            button: button,

            // http://rancher/env/1a5/infra/hosts/1h69
            hostUrl: function() {
                return button.parentNode.parentNode.querySelector('td[data-title="Primary Host:"]').querySelector("a").href;
            },
            hostId: function() {
                return this.hostUrl().split("/").pop();
            },

            // http://rancher/env/1a5/infra/containers/1i325997
            containerUrl: function() {
                return button.parentNode.parentNode.querySelector('td[data-title="Name:"]').querySelector("a").href;
            },
            containerId: function() {
                return this.containerUrl().split("/").pop();
            }
        };
        return container;
    }

    function openColorbox(url, title) {
      var cssId = 'colorbox.css';
      if (!document.getElementById(cssId)) {
          var link  = document.createElement('link');
          link.id   = cssId;
          link.rel  = 'stylesheet';
          link.type = 'text/css';
          link.href = 'http://www.jacklmoore.com/colorbox/example5/colorbox.css';
          link.media = 'all';
          document.getElementsByTagName('head')[0].appendChild(link);
      }
      $.colorbox({
        open: true,
        iframe:true,
        width:"80%",
        height:"80%",
        href: url,
        onClosed: function(){
          $.colorbox.remove();
        }
      });
    }

    function openIframe(url, title) {
        var div = document.createElement("div");
        var inner = document.createElement("div");
        var cbox = document.createElement("div");
        var iframe = document.createElement("iframe");
        var footer = document.createElement("div");
        var footer_status = document.createElement("div");
        var footer_actions = document.createElement("div");
        var footer_button = document.createElement("button");
        footer.classList.add("footer-actions");
        footer_status.classList.add("console-status", "text-muted");
        footer_actions.classList.add("footer-actions");
        footer_button.classList.add("btn", "btn-primary");
        footer.appendChild(footer_status);
        footer.appendChild(footer_actions);
        footer_actions.appendChild(footer_button);

        // destroy-iframe event.
        div.addEventListener('destroy-iframe', function (e) {
            iframe.parentNode.removeChild(iframe);
            this.parentNode.removeChild(this);
        }, false);

        footer_button.addEventListener('click', function (e) {
            div.dispatchEvent(new Event('destroy-iframe'));
            e.stopPropagation();
        }, false);

        iframe.src = url;
        iframe.setAttribute("style", "overflow:hidden;width:100%;height:80vh;");
        inner.classList.add("lacsso", "modal-container", "large-modal");
        div.classList.add("lacsso", "modal-overlay", "modal-open");
        cbox.setAttribute("style", "height:100%");

        document.body.appendChild(div);
        div.appendChild(inner);
        inner.appendChild(cbox);
        cbox.appendChild(iframe);
        cbox.appendChild(footer);
    }

    function openWindow(url, title) {
        window.open(url, title, 'directories=no,titlebar=yes,menubar=no,toolbar=no,location=no,personalbar=no,status=no,scrollbars=no,resizable=yes,width=950,height=950');
    }

    function findActionTarget(element) {
        var button = document.getElementsByClassName('ember-view btn-group resource-actions action-menu open');

        if (button) {
            var container = new Container(button[0]);
            var url = "http://localhost:57575/session/" + container.containerId();
            var title = container.containerId() + 'terminal';
            openIframe(url, title);
        }
    }

    var resActions = false;

    function resourceActions() {
        if (!resActions && document.getElementById('resource-actions')) {
            document.getElementById('resource-actions').addEventListener("click", function(e) {
                findActionTarget(e);
                e.stopPropagation();
            });
            resActions = true;
        }
    }

    document.addEventListener("DOMSubtreeModified", function(e){
        resourceActions(e.target);
    }, false);
    var cssId = 'colorbox.css';
    if (!document.getElementById(cssId)) {
        var link  = document.createElement('link');
        link.id   = cssId;
        link.rel  = 'stylesheet';
        link.type = 'text/css';
        link.href = 'http://www.jacklmoore.com/colorbox/example5/colorbox.css';
        link.media = 'all';
        document.getElementsByTagName('head')[0].appendChild(link);
    }
})();
