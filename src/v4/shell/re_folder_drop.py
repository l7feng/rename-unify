"""Native WebView2 folder paths for the project output input."""
import json
import time


def bind_project_drop(window):
    from webview.dom import DOMEventHandler

    def receive(event):
        files = event.get('dataTransfer', {}).get('files', [])
        # Full paths are supplied by WebView2, never guessed from File.name.
        if not files:
            return  # Text paths are handled by the ordinary DOM listener.
        paths = [item.get('pywebviewFullPath', '') for item in files]
        window.evaluate_js('window.RenameProjectDrop.receive(%s)' % json.dumps(paths))

    try:
        # Native loaded and page scripts may finish on different threads.
        for _ in range(50):
            if window.evaluate_js('!!(window.RenameProjectDrop && window.pywebview && window.pywebview._getNodeId && document.getElementById("ftOutRoot"))'):
                break
            time.sleep(.1)
        else:
            raise RuntimeError('folder drop page not ready')
        element = window.dom.get_element('#ftOutRoot')
        if element is None:
            raise RuntimeError('output input not found')
        element.on('drop', DOMEventHandler(receive, prevent_default=True))
        window.evaluate_js('window.RenameProjectDrop.setNativeReady(true)')
    except Exception as exc:
        window.evaluate_js('window.RenameProjectDrop.setNativeReady(false, %s)' % json.dumps(str(exc)))
        print('[re-drop] registration failed: %s' % exc)
