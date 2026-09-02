# -*- coding: utf-8 -*-
import os
import logging
import bpy
from ..pfade import Projektpfade
logger = logging.getLogger(__name__)


class HUMANBODY_OT_mocapnet_webui(bpy.types.Operator):
    bl_idname = "humanbody.mocapnet_webui"
    bl_label = "MocapNET Web-UI"
    bl_description = "Start MocapNET Django server and open web UI for video-to-BVH processing"
    bl_options = {'REGISTER'}

    _WEBAPP_DIR = str(Projektpfade.webapp())
    _PORT = 8081

    def execute(self, context):
        import subprocess
        import webbrowser
        import socket

        # Check if server is already running
        running = False
        try:
            with socket.create_connection(("127.0.0.1", self._PORT), timeout=1):
                running = True
        # stumm gewollt: Genau das ist die Antwort: Wer nicht annimmt, laeuft
        # nicht. Ein Log je Pruefung waere Rauschen.
        except (ConnectionRefusedError, OSError):
            pass

        if not running:
            manage_py = os.path.join(self._WEBAPP_DIR, "manage.py")
            if not os.path.isfile(manage_py):
                self.report({'ERROR'}, f"Django project not found at {self._WEBAPP_DIR}")
                return {'CANCELLED'}
            subprocess.Popen(
                ["python", manage_py, "runserver", str(self._PORT)],
                cwd=self._WEBAPP_DIR,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.report({'INFO'}, f"MocapNET server started on port {self._PORT}")
        else:
            self.report({'INFO'}, "MocapNET server already running")

        webbrowser.open(f"http://127.0.0.1:{self._PORT}/")
        return {'FINISHED'}
