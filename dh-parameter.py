#!/usr/bin/env python3
#
# parameter-viewer by Oliver Dippel
#
#  Denavit-Hartenberg (DH) parameters for genserkins
#  experimental !
#


import argparse
import platform
import math
import signal
import sys

from OpenGL import GL
from HersheyFonts.HersheyFonts import HersheyFonts

from PyQt5.QtOpenGL import QGLFormat, QGLWidget  # pylint: disable=E0611
from PyQt5.QtWidgets import (  # pylint: disable=E0611
    QApplication,
    QLabel,
    QHBoxLayout,
    QMessageBox,
    QPlainTextEdit,
    QDoubleSpinBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

hal = """
setp genserkins.A-0 0.0
setp genserkins.ALPHA-0 0.0
setp genserkins.D-0 350.0
setp genserkins.A-1 85.0
setp genserkins.ALPHA-1 -1.571
setp genserkins.D-1 0.0
setp genserkins.A-2 380.0
setp genserkins.ALPHA-2 0.0
setp genserkins.D-2 0.0
setp genserkins.A-3 100.0
setp genserkins.ALPHA-3 -1.571
setp genserkins.D-3 425.0
setp genserkins.A-4 0.0
setp genserkins.ALPHA-4 1.571
setp genserkins.D-4 0.0
setp genserkins.A-5 0.0
setp genserkins.ALPHA-5 -1.571
setp genserkins.D-5 0.0
"""
parameter = {}

font = HersheyFonts()
font.load_default_font()
font.normalize_rendering(6)


class GLWidget(QGLWidget):
    """customized GLWidget."""

    min_max = (-500, -500, 500, 500)

    GL_MULTISAMPLE = 0x809D
    version_printed = False
    screen_w = 100
    screen_h = 100
    aspect = 1.0
    rot_x = -20.0
    rot_y = -30.0
    rot_z = 0.0
    rot_x_last = rot_x
    rot_y_last = rot_y
    rot_z_last = rot_z
    trans_x = 0.0
    trans_y = 0.0
    trans_z = 0.0
    trans_x_last = trans_x
    trans_y_last = trans_y
    trans_z_last = trans_z
    scale_xyz = 1.0
    scale = 1.0
    scale_last = scale
    ortho = False
    mbutton = None
    mpos = None
    mouse_pos_x = 0
    mouse_pos_y = 0
    selector_mode = ""
    selection = ()
    selection_set = ()
    size_x = 0
    size_y = 0
    retina = False
    wheel_scale = 0.1

    def __init__(self, parent=None):
        """init function."""
        self.parent = parent
        self.oldout = ""
        my_format = QGLFormat.defaultFormat()
        my_format.setSampleBuffers(True)
        QGLFormat.setDefaultFormat(my_format)
        if not QGLFormat.hasOpenGL():
            QMessageBox.information(
                self.project["window"],
                "OpenGL using samplebuffers",
                "This system does not support OpenGL.",
            )
            sys.exit(0)

        super(GLWidget, self).__init__()
        self.startTimer(40)
        self.setMouseTracking(True)
        if platform.system().lower() == "darwin":
            self.retina = not call(
                "system_profiler SPDisplaysDataType 2>/dev/null | grep -i 'retina' >/dev/null",
                shell=True,
            )
        self.wheel_scale = 0.005 if self.retina else 0.1

    def initializeGL(self) -> None:  # pylint: disable=C0103
        """glinit function."""

        version = GL.glGetString(GL.GL_VERSION).decode()
        if not self.version_printed:
            print(f"OpenGL-Version: {version}")
            self.version_printed = True

        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()

        if self.frameGeometry().width() == 0:
            self.aspect = 1.0
        else:
            self.aspect = self.frameGeometry().height() / self.frameGeometry().width()

        height = 0.2
        width = height * self.aspect

        if self.ortho:
            GL.glOrtho(
                -height * 2.5, height * 2.5, -width * 2.5, width * 2.5, -1000, 1000
            )
        else:
            GL.glFrustum(-height, height, -width, width, 0.5, 100.0)

        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()
        GL.glClearColor(0.0, 0.0, 0.0, 1.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glClearDepth(1.0)
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDisable(GL.GL_CULL_FACE)
        GL.glDepthFunc(GL.GL_LEQUAL)
        GL.glDepthMask(GL.GL_TRUE)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glEnable(GL.GL_COLOR_MATERIAL)
        GL.glColorMaterial(GL.GL_FRONT_AND_BACK, GL.GL_AMBIENT_AND_DIFFUSE)
        if int(version.split(".")[0]) >= 2:
            GL.glEnable(GL.GL_RESCALE_NORMAL)
            GL.glEnable(GLWidget.GL_MULTISAMPLE)
        GL.glLight(GL.GL_LIGHT0, GL.GL_POSITION, (0, 0, 0, 1))
        GL.glLightfv(GL.GL_LIGHT0, GL.GL_AMBIENT, (0.1, 0.1, 0.1, 1))
        GL.glLightfv(GL.GL_LIGHT0, GL.GL_DIFFUSE, (1, 1, 1, 1))
        GL.glEnable(GL.GL_LIGHTING)
        GL.glEnable(GL.GL_LIGHT0)

    def resizeGL(self, width, height) -> None:  # pylint: disable=C0103
        """glresize function."""
        if self.retina:
            self.screen_w = width / 2
            self.screen_h = height / 2
        else:
            self.screen_w = width
            self.screen_h = height
        GL.glViewport(0, 0, width, height)
        self.initializeGL()

    def paintGL(self) -> None:  # pylint: disable=C0103
        """glpaint function."""

        GL.glNormal3f(0, 0, 1)

        self.size_x = max(self.min_max[2] - self.min_max[0], 0.1)
        self.size_y = max(self.min_max[3] - self.min_max[1], 0.1)
        self.scale = min(1.0 / self.size_x, 1.0 / self.size_y) / 1.4

        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
        GL.glMatrixMode(GL.GL_MODELVIEW)

        GL.glPushMatrix()
        GL.glTranslatef(-self.trans_x, -self.trans_y, self.trans_z - 1.2)
        GL.glScalef(self.scale_xyz, self.scale_xyz, self.scale_xyz)
        GL.glRotatef(self.rot_x, 0.0, 1.0, 0.0)
        GL.glRotatef(self.rot_y, 1.0, 0.0, 0.0)
        GL.glRotatef(self.rot_z, 0.0, 0.0, 1.0)
        GL.glTranslatef(
            (-self.size_x / 2.0 - self.min_max[0]) * self.scale,
            (-self.size_y / 2.0 - self.min_max[1]) * self.scale,
            0.0,
        )
        GL.glScalef(self.scale, self.scale, self.scale)

        GL.glNormal3f(0, 0, 1)

        # Grid-X
        grid_size = 100
        GL.glLineWidth(0.5)
        GL.glColor3f(0.9, 0.9, 0.9)
        GL.glBegin(GL.GL_LINES)
        for p_x in range(self.min_max[0], self.min_max[2] + grid_size, grid_size):
            GL.glVertex3f(p_x, self.min_max[1], 0)
            GL.glVertex3f(p_x, self.min_max[3], 0)
        GL.glEnd()

        # Grid-Y
        GL.glLineWidth(0.5)
        GL.glColor3f(0.9, 0.9, 0.9)
        GL.glBegin(GL.GL_LINES)
        for p_y in range(self.min_max[1], self.min_max[3] + grid_size, grid_size):
            GL.glVertex3f(self.min_max[0], p_y, 0)
            GL.glVertex3f(self.min_max[2], p_y, 0)
        GL.glEnd()

        GL.glLineWidth(5)
        GL.glColor4f(0.0, 1.0, 0.0, 1.0)
        GL.glBegin(GL.GL_LINES)
        GL.glVertex3f(-20.0, -20.0, 0.0)
        GL.glVertex3f(20.0, 20.0, 0.0)
        GL.glVertex3f(20.0, -20.0, 0.0)
        GL.glVertex3f(-20.0, 20.0, 0.0)
        GL.glEnd()

        text_scale = 5.0
        circle_off = 20.0
        circle_rad = 20.0
        angle = 0.0
        next_point = [0.0, 0.0, 0.0]
        last_point = [0.0, 0.0, 0.0]

        config = []
        for joint in range(6):
            param_a = parameter[f"A-{joint}"].value()
            param_alpha = parameter[f"ALPHA-{joint}"].value()
            param_d = parameter[f"D-{joint}"].value()
            config.append(f"setp genserkins.A-{joint} {param_a}")
            config.append(f"setp genserkins.ALPHA-{joint} {param_alpha}")
            config.append(f"setp genserkins.D-{joint} {param_d}")

            angle += parameter[f"ALPHA-{joint}"].value()
            next_point[0] += parameter[f"A-{joint}"].value() * math.sin(math.pi / 2)
            next_point[2] += parameter[f"A-{joint}"].value() * math.cos(math.pi / 2)

            GL.glLineWidth(15)
            GL.glColor4f(0.0, 1.0, 1.0, 1.0)
            GL.glBegin(GL.GL_LINES)
            GL.glVertex3f(last_point[0], last_point[1], last_point[2])
            GL.glVertex3f(next_point[0], next_point[1], next_point[2])
            GL.glEnd()
            last_point = next_point.copy()

            next_point[0] += parameter[f"D-{joint}"].value() * math.sin(angle)
            next_point[2] += parameter[f"D-{joint}"].value() * math.cos(angle)

            last_c = None
            if joint in {0, 4}:
                GL.glLineWidth(5)
                GL.glColor4f(0.0, 0.0, 1.0, 1.0)
                GL.glBegin(GL.GL_LINES)
                mid_z = last_point[2] + (next_point[2] - last_point[2]) / 2
                for n in range(100 + 1):
                    a = math.pi * 2 / 100 * n
                    ex = next_point[0] + circle_rad * math.sin(a)
                    ey = next_point[1] + circle_rad * math.cos(a)
                    next_c = (ex, ey, mid_z)
                    if last_c:
                        GL.glVertex3f(*last_c)
                        GL.glVertex3f(*next_c)
                    last_c = next_c
                GL.glEnd()

                GL.glLineWidth(1)
                GL.glColor3f(0.9, 0.9, 0.9)
                GL.glBegin(GL.GL_LINES)
                draw_text(
                    f"{joint}",
                    next_point[0],
                    next_point[1],
                    mid_z,
                    text_scale,
                    True,
                    True,
                )
                GL.glEnd()

            else:
                GL.glLineWidth(5)
                GL.glColor4f(1.0, 0.0, 1.0, 1.0)
                GL.glBegin(GL.GL_LINES)
                for n in range(100 + 1):
                    a = math.pi * 2 / 100 * n
                    ex = next_point[0] + circle_rad * math.sin(a)
                    ez = next_point[2] + circle_rad * math.cos(a)
                    next_c = (ex, next_point[1] + 30, ez)
                    if last_c:
                        GL.glVertex3f(*last_c)
                        GL.glVertex3f(*next_c)

                    last_c = next_c
                GL.glEnd()

                GL.glLineWidth(1)
                GL.glColor3f(0.9, 0.9, 0.9)
                GL.glBegin(GL.GL_LINES)
                draw_text(
                    f"{joint}",
                    next_point[0],
                    next_point[1] + circle_off,
                    next_point[2],
                    text_scale,
                    True,
                    True,
                )
                GL.glEnd()

            GL.glLineWidth(15)
            GL.glColor4f(0.0, 1.0, 1.0, 1.0)
            GL.glBegin(GL.GL_LINES)
            GL.glVertex3f(last_point[0], last_point[1], last_point[2])
            GL.glVertex3f(next_point[0], next_point[1], next_point[2])
            GL.glEnd()
            GL.glLineWidth(5)

            if joint not in {0, 4}:
                GL.glColor4f(1.0, 0.0, 0.0, 1.0)
                GL.glBegin(GL.GL_LINES)
                GL.glVertex3f(next_point[0], next_point[1] - circle_off, next_point[2])
                GL.glVertex3f(next_point[0], next_point[1] + circle_off, next_point[2])
                GL.glEnd()
            else:
                GL.glColor4f(1.0, 1.0, 1.0, 0.5)
                GL.glBegin(GL.GL_LINES)
                GL.glVertex3f(next_point[0], next_point[1] - circle_off, next_point[2])
                GL.glVertex3f(next_point[0], next_point[1] + circle_off, next_point[2])
                GL.glEnd()

            last_point = next_point.copy()

        GL.glPopMatrix()

        new = "\n".join(config).strip()
        if new != self.oldout:
            self.parent.output.clear()
            self.parent.output.insertPlainText(new)
            self.oldout = new

    def timerEvent(self, event) -> None:  # pylint: disable=C0103,W0613
        """gltimer function."""
        self.update()

    def mousePressEvent(self, event) -> None:  # pylint: disable=C0103
        """mouse button pressed."""
        self.mbutton = event.button()
        self.mpos = event.pos()
        self.rot_x_last = self.rot_x
        self.rot_y_last = self.rot_y
        self.rot_z_last = self.rot_z
        self.trans_x_last = self.trans_x
        self.trans_y_last = self.trans_y
        self.trans_z_last = self.trans_z

    def mouseReleaseEvent(self, event) -> None:  # pylint: disable=C0103,W0613
        """mouse button released."""
        self.mbutton = None
        self.mpos = None

    def mouseMoveEvent(self, event) -> None:  # pylint: disable=C0103
        """mouse moved."""
        if self.mbutton == 1:
            moffset = self.mpos - event.pos()
            self.trans_x = self.trans_x_last + moffset.x() / self.screen_w
            self.trans_y = self.trans_y_last - moffset.y() / self.screen_h * self.aspect
        elif self.mbutton == 2:
            moffset = self.mpos - event.pos()
            self.rot_z = self.rot_z_last - moffset.x() / 4
            self.trans_z = self.trans_z_last + moffset.y() / 500
            if self.ortho:
                self.ortho = False
                self.initializeGL()
        elif self.mbutton == 4:
            moffset = self.mpos - event.pos()
            self.rot_x = self.rot_x_last + -moffset.x() / 4
            self.rot_y = self.rot_y_last - moffset.y() / 4
            if self.ortho:
                self.ortho = False
                self.initializeGL()

    def wheelEvent(self, event) -> None:  # pylint: disable=C0103,W0613
        """mouse wheel moved."""
        if event.angleDelta().y() > 0:
            self.scale_xyz += self.wheel_scale
        else:
            self.scale_xyz -= self.wheel_scale


def draw_text(
    text: str,
    pos_x: float,
    pos_y: float,
    pos_z: float,
    scale: float = 1.0,
    center_x: bool = False,
    center_y: bool = False,
) -> None:
    test_data = tuple(font.lines_for_text(text))
    if center_x or center_y:
        width = 0.0
        height = 0.0
        for (x_1, y_1), (x_2, y_2) in test_data:
            width = max(width, x_1 * scale)
            width = max(width, x_2 * scale)
            height = max(height, y_1 * scale)
            height = max(height, y_2 * scale)
        if center_x:
            pos_x -= width / 2.0
        if center_y:
            pos_y -= height / 2.0
    for (x_1, y_1), (x_2, y_2) in test_data:
        GL.glVertex3f(pos_x + x_1 * scale, pos_y + y_1 * scale, pos_z)
        GL.glVertex3f(pos_x + x_2 * scale, pos_y + y_2 * scale, pos_z)


class WinForm(QWidget):
    def __init__(self, args, parent=None):
        global hal
        super(WinForm, self).__init__(parent)
        self.setWindowTitle("Denavit-Hartenberg - Viewer")
        layoutMain = QHBoxLayout()
        self.setLayout(layoutMain)
        # self.resize(1900, 1200)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        layoutleft = QVBoxLayout()
        layoutMain.addLayout(layoutleft)

        self.view3d = GLWidget(self)
        self.view3d.setFixedWidth(800)
        self.view3d.setFixedHeight(600)
        layoutMain.addWidget(self.view3d)

        layoutright = QVBoxLayout()
        layoutMain.addLayout(layoutright)

        self.output = QPlainTextEdit()
        layoutright.addWidget(self.output)

        if args.halfile:
            print(f"loading params from halfile: {args.halfile}")
            hal = open(args.halfile, "r").read()

        for line in hal.split("\n"):
            if not line.startswith("setp genserkins."):
                continue
            key = line.split()[1].split(".")[1]
            value = float(line.split()[-1])

            vbox = QHBoxLayout()
            layoutleft.addLayout(vbox)
            vbox.addWidget(QLabel(f"{key}:"))
            dspinbox = QDoubleSpinBox()
            dspinbox.setMinimum(-9999999999.0)
            dspinbox.setMaximum(9999999999.0)
            dspinbox.setDecimals(3)
            if key.startswith("ALPHA"):
                dspinbox.setSingleStep(0.1)
            else:
                dspinbox.setSingleStep(1.0)
            dspinbox.setValue(value)
            parameter[key] = dspinbox
            vbox.addWidget(dspinbox)

        exitbutton = QPushButton("&Exit")
        exitbutton.clicked.connect(self.exit_callback)
        layoutleft.addWidget(exitbutton)

    def exit_callback(self):
        exit(0)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    parser = argparse.ArgumentParser()
    parser.add_argument("halfile", help="halfile", nargs="?", type=str, default=None)
    args = parser.parse_args()
    form = WinForm(args)
    form.show()

    sys.exit(app.exec_())
