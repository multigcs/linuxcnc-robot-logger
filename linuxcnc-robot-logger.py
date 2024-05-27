#!/usr/bin/env python3
#
# LinuxCNC logger by Oliver Dippel
#
#  especially for robots
#

import argparse
import os
import signal
import sys
from datetime import datetime
from functools import partial

import linuxcnc
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

MODE_NAME = ["WORLD", "JOINT"]
AXIS_NAMES = ["X", "Y", "Z", "A", "B", "C", "U", "V", "W"]

# http://linuxcnc.org/docs/master/html/de/config/python-interface.html
s = linuxcnc.stat()
c = linuxcnc.command()

class WinForm(QWidget):
    def __init__(self, args, parent=None):
        super(WinForm, self).__init__(parent)
        self.setWindowTitle("LinuxCNC-Logger (for Robots)")
        layoutMain = QHBoxLayout()
        self.setLayout(layoutMain)
        # self.resize(1900, 1200)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        layoutleft = QVBoxLayout()
        layoutMain.addLayout(layoutleft)
        self.logview = QPlainTextEdit()
        self.logview.setFixedWidth(450)
        layoutMain.addWidget(self.logview)
        layoutright = QVBoxLayout()
        layoutMain.addLayout(layoutright)

        # axis self.checkboxes
        self.checkboxes = {}
        axislay = QHBoxLayout()
        layoutleft.addLayout(axislay)
        wlay = QVBoxLayout()
        wlay.addWidget(QLabel("Axis"))
        axislay.addLayout(wlay)
        for an, name in enumerate(AXIS_NAMES):
            self.checkboxes[f"W_{name}"] = QCheckBox(name)
            if an < 3:
                self.checkboxes[f"W_{name}"].setChecked(True)
            wlay.addWidget(self.checkboxes[f"W_{name}"])
        jlay = QVBoxLayout()
        jlay.addWidget(QLabel("Joint"))
        axislay.addLayout(jlay)
        for jn, name in enumerate(AXIS_NAMES):
            self.checkboxes[f"J_{name}"] = QCheckBox(f"{jn}")
            self.checkboxes[f"J_{name}"].setChecked(True)
            jlay.addWidget(self.checkboxes[f"J_{name}"])

        addbutton = QPushButton("\n&Add\n")
        addbutton.clicked.connect(self.add_callback)
        layoutleft.addWidget(addbutton)

        pausebutton = QPushButton("\n&Pause\n")
        pausebutton.clicked.connect(self.pause_callback)
        layoutleft.addWidget(pausebutton)

        layoutleft.addWidget(QLabel("Comment:"))
        self.commentline = QLineEdit()
        self.commentline.setFixedWidth(250)
        self.commentline.returnPressed.connect(self.comment_callback)
        layoutleft.addWidget(self.commentline)

        layoutleft.addStretch()

        snaplabel = QLabel("Snap-Tolerance:")
        snaplabel.setFixedWidth(220)
        layoutleft.addWidget(snaplabel)
        self.snaptol = QLineEdit()
        self.snaptol.setFixedWidth(250)
        self.snaptol.setText("5.0")
        layoutleft.addWidget(self.snaptol)

        self.snap = {}
        layoutleft.addWidget(QLabel("Snap-Values:"))
        for axis in ("X", "Y", "Z"):
            snaplay = QHBoxLayout()
            layoutleft.addLayout(snaplay)
            snaplabel = QLabel(axis)
            snaplabel.setFixedWidth(20)
            snaplay.addWidget(snaplabel)
            self.snap[axis] = QLineEdit()
            self.snap[axis].setFixedWidth(150)
            snaplay.addWidget(self.snap[axis])
            snapbtn = QPushButton("ADD")
            snapbtn.setFixedWidth(40)
            cb = partial(self.snapadd_callback, axis)
            snapbtn.clicked.connect(cb)
            snaplay.addWidget(snapbtn)

        layoutleft.addStretch()

        savebutton = QPushButton("\n&Save\n")
        savebutton.clicked.connect(self.save_callback)
        layoutleft.addWidget(savebutton)

        resetbutton = QPushButton("&Reset")
        resetbutton.clicked.connect(self.reset_callback)
        layoutleft.addWidget(resetbutton)

        exitbutton = QPushButton("&Exit")
        exitbutton.clicked.connect(self.exit_callback)
        layoutleft.addWidget(exitbutton)

        if not args.no_autoupdate:
            self.coords_w = {}
            self.mode_world_label = QLabel("World:")
            layoutright.addWidget(self.mode_world_label)
            for axis in AXIS_NAMES:
                coordslay = QHBoxLayout()
                layoutright.addLayout(coordslay)
                coordslabel = QLabel(axis)
                coordslabel.setFixedWidth(20)
                coordslay.addWidget(coordslabel)
                self.coords_w[axis] = QLineEdit()
                self.coords_w[axis].setFixedWidth(150)
                coordslay.addWidget(self.coords_w[axis])

                snapbtn = QPushButton("GO")
                snapbtn.setFixedWidth(40)
                cb = partial(self.snapgo_callback, axis)
                snapbtn.clicked.connect(cb)
                coordslay.addWidget(snapbtn)


            self.coords_j = {}
            self.mode_joint_label = QLabel("Joints:")
            layoutright.addWidget(self.mode_joint_label)
            for axis in AXIS_NAMES:
                coordslay = QHBoxLayout()
                layoutright.addLayout(coordslay)
                coordslabel = QLabel(axis)
                coordslabel.setFixedWidth(20)
                coordslay.addWidget(coordslabel)
                self.coords_j[axis] = QLineEdit()
                self.coords_j[axis].setFixedWidth(150)
                coordslay.addWidget(self.coords_j[axis])


            layoutright.addStretch()

        self.reset_callback()

        if args.check:
            gcode = self.logview.toPlainText()
            print(gcode)

            exit(0)

        self.commentline.setFocus()

        if not args.no_autoupdate:
            self.timer = QTimer()
            self.timer.timeout.connect(self.runTimer)
            self.timer.start(500)


    def ok_for_mdi(self):
        return not s.estop and s.enabled and (s.homed.count(1) == s.joints) and (s.interp_state == linuxcnc.INTERP_IDLE)

    def snapgo_callback(self, axis):
        if self.ok_for_mdi():
            c.mode(linuxcnc.MODE_MDI)
            c.wait_complete()
            c.mdi(f"G0 {axis}{self.pos_w[AXIS_NAMES.index(axis)]}")

    def statusUpdate(self):
        try:
            s.poll()
        except Exception as err:
            print(f"can not poll linuxcnc: {err}")
            return

        # check coords mode (world/joint)
        if not args.joints:
            self.mode = s.aout[3]
        else:
            self.mode = 0.0

        # get joint positions
        # need to update this offsets in Joint-Mode, not available in World-Mode :(
        offsets_g5x = (0.0, -90.0, 0.0, 0.0, 90.0, 0.0, 0.0, 0.0, 0.0)
        for n, pos in enumerate(s.joint_position):
            if n >= len(s.axis):
                break
            if not self.checkboxes[f"J_{AXIS_NAMES[n]}"].isChecked():
                continue
            if (
                s.axis[n]["min_position_limit"] != 0
                and s.axis[n]["max_position_limit"] != 0
            ):
                position = round(pos - offsets_g5x[n] - s.g92_offset[n], 2)
                self.pos_j[n] = position

        if args.joints or self.mode == 1.0:
            pass
        else:
            # get axis positions
            for n, pos in enumerate(s.position):
                if not self.checkboxes[f"W_{AXIS_NAMES[n]}"].isChecked():
                    continue
                if (
                    s.axis[n]["min_position_limit"] != 0
                    and s.axis[n]["max_position_limit"] != 0
                ):
                    position = round(pos, 2)
                    position = round(pos - s.g5x_offset[n] - s.g92_offset[n], 2)
                    position_raw = position

                    # snap positions
                    sflag = False
                    snap_limit = float(self.snaptol.text())
                    if AXIS_NAMES[n] in self.snap:
                        snap_positions = self.snap[AXIS_NAMES[n]].text()
                        for pos in snap_positions.split():
                            diff = abs(float(pos) - position)
                            if diff <= snap_limit:
                                position = float(pos)
                                sflag = True
                                break

                    self.pos_w[n] = position
                    self.pos_wr[n] = position_raw
                    self.pos_ws[n] = sflag

    def runTimer(self):
        self.statusUpdate()

        if self.pulse == "*":
            self.pulse = " "
        else:
            self.pulse = "*"

        if self.mode == 0:
            self.mode_world_label.setText(f"World: (ACTIVE) {self.pulse}")
            self.mode_world_label.setStyleSheet("color: green;")
            self.mode_joint_label.setText(f"Joint: {self.pulse}")
            self.mode_joint_label.setStyleSheet("color: blue;")
        elif self.mode == 1:
            self.mode_world_label.setText("World:")
            self.mode_world_label.setStyleSheet("color: red;")
            self.mode_joint_label.setText(f"Joint: (ACTIVE) {self.pulse}")
            self.mode_joint_label.setStyleSheet("color: green;")

        for n, _pos in enumerate(s.joint_position):
            if n >= len(s.axis):
                break
            if not self.checkboxes[f"J_{AXIS_NAMES[n]}"].isChecked():
                self.coords_j[AXIS_NAMES[n]].setText("")
                continue
            if (
                s.axis[n]["min_position_limit"] != 0
                and s.axis[n]["max_position_limit"] != 0
            ):
                self.coords_j[AXIS_NAMES[n]].setText(f"{self.pos_j[n]}")

        if args.joints or self.mode == 1.0:
            pass
        else:
            # get axis positions
            for n, _pos in enumerate(s.position):
                if not self.checkboxes[f"W_{AXIS_NAMES[n]}"].isChecked():
                    self.coords_w[AXIS_NAMES[n]].setText("")
                    continue
                if (
                    s.axis[n]["min_position_limit"] != 0
                    and s.axis[n]["max_position_limit"] != 0
                ):

                    if self.pos_ws[n]:
                        self.coords_w[AXIS_NAMES[n]].setStyleSheet("color: green;")
                        self.coords_w[AXIS_NAMES[n]].setText(
                            f"{self.pos_wr[n]} ({self.pos_w[n]})"
                        )
                    else:
                        self.coords_w[AXIS_NAMES[n]].setStyleSheet("color: black;")
                        self.coords_w[AXIS_NAMES[n]].setText(f"{self.pos_w[n]}")

    def snapadd_callback(self, axis):
        self.statusUpdate()

        pos = self.pos_w[AXIS_NAMES.index(axis)]

        tol = float(self.snaptol.text())
        if pos is not None:
            if tol >= 1:
                pos = round(pos, 0)
            else:
                pos = round(pos, 1)
            old = self.snap[axis].text()
            if str(pos) not in old:
                self.snap[axis].setText(f"{old} {pos}")
        self.commentline.setFocus()

    def comment_callback(self):
        comment = self.commentline.text()
        self.commentline.setText("")

        if comment == "p":
            self.pause_callback()
        elif comment:
            self.addcode(f"\n({comment})")
        else:
            self.add_callback()

    def reset_callback(self):
        self.pulse = " "
        self.mode = None
        self.last_mode = None
        self.pos_w = [None] * 9
        self.pos_ws = [False] * 9
        self.pos_wr = [None] * 9
        self.last_pos_w = [None] * 9
        self.pos_j = [None] * 9
        self.last_pos_j = [None] * 9
        self.last_aout = [0.0] * 64
        self.last_dout = [0] * 64
        self.logview.clear()

        gcode = ""
        if os.path.isfile(args.filename[0]):
            # loading gcode from existing file
            gcode = open(args.filename[0], "r").read()
        if gcode:
            # remove programm end (M02)
            gcode += "\n(reopen)"
            self.logview.insertPlainText(gcode)
        else:
            # initial code
            self.logview.insertPlainText("G21   (Metric/mm)\n")
            self.logview.insertPlainText("G40   (No Offsets)\n")
            self.logview.insertPlainText("G90   (Absolute-Mode)\n")
            self.logview.insertPlainText("M05   (Spindle off)\n")
            self.logview.insertPlainText("F1000 (Feedrate)\n")
            if args.joints:
                # switch to joint mode
                self.logview.insertPlainText("M429\n")

        self.add_callback()

    def pause_callback(self):
        self.addcode("\nG4 P1 (pause)")

    def add_callback(self):
        self.statusUpdate()

        gcode = [f"\n({datetime.now()})"]

        # check coords mode (world/joint)
        mode = 0.0
        if not args.joints:
            mode = s.aout[3]
            if mode != self.last_mode:
                if mode == 0:
                    gcode.append(f"\nM428 ({MODE_NAME[int(mode)]}-COORDS)")
                elif mode == 1:
                    gcode.append(f"\nM429 ({MODE_NAME[int(mode)]}-COORDS)")
                self.last_mode = mode

        gcode.append("\nG0")
        if args.joints or mode == 1.0:
            for n, _pos in enumerate(s.joint_position):
                if n >= len(s.axis):
                    break
                if not self.checkboxes[f"J_{AXIS_NAMES[n]}"].isChecked():
                    continue
                if (
                    s.axis[n]["min_position_limit"] != 0
                    and s.axis[n]["max_position_limit"] != 0
                ):
                    position = self.pos_j[n]
                    if position != self.last_pos_j[n]:
                        gcode.append(f" {AXIS_NAMES[n]}{position}")
                        self.last_pos_j[n] = position
        else:
            # get axis positions
            for n, _pos in enumerate(s.position):
                if not self.checkboxes[f"W_{AXIS_NAMES[n]}"].isChecked():
                    continue
                if (
                    s.axis[n]["min_position_limit"] != 0
                    and s.axis[n]["max_position_limit"] != 0
                ):
                    position = self.pos_w[n]
                    if position != self.last_pos_w[n]:
                        gcode.append(f" {AXIS_NAMES[n]}{position}")
                        self.last_pos_w[n] = position

        # analog outputs
        for n, value in enumerate(s.aout):
            if n == 3:
                # in robot mode, we can read the kinstype here
                continue
            if value != self.last_aout[n]:
                self.last_aout[n] = value
                gcode.append(f"\nM68 E{n} Q{value} (analog-out)")
                gcode.append("\nG4 P0.5 (pause)")

        # digital outputs
        for n, value in enumerate(s.dout):
            if n == 3:
                # in robot mode, we can read the kinstype here
                continue
            if value != self.last_dout[n]:
                self.last_dout[n] = value
                if value == 1:
                    gcode.append(f"\nM64 P{n} (digital-out on)")
                else:
                    gcode.append(f"\nM65 P{n} (digital-out off)")
                gcode.append("\nG4 P0.1 (pause)")

        # add changes
        if len(gcode) > 2:
            gcode.append("\n")
            self.addcode("".join(gcode))
        else:
            self.commentline.setFocus()

    def addcode(self, new_code):
        # clean
        rawtext = self.logview.toPlainText()
        lines = []
        for line in rawtext.split("\n"):
            if line and line[0] not in {"(", "G", "M", "F"}:
                line = f"({line})"
            if not line.startswith("M02"):
                lines.append(f"{line}\n")

        lines.append(new_code)
        lines.append("\nM02\n")
        gcode_string = "".join(lines)

        self.logview.clear()
        self.logview.insertPlainText(gcode_string)

        # scroll to bottom
        self.logview.verticalScrollBar().setValue(
            self.logview.verticalScrollBar().maximum()
        )

        self.commentline.setFocus()

    def exit_callback(self):
        exit(0)

    def save_callback(self):
        gcode = self.logview.toPlainText()
        open(args.filename[0], "w").write(gcode)
        self.commentline.setFocus()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--joints", "-j", help="joints", default=False, action="store_true"
    )
    parser.add_argument(
        "--check", "-c", help="check", default=False, action="store_true"
    )
    parser.add_argument(
        "--no-autoupdate",
        "-n",
        help="no autoupdate",
        default=False,
        action="store_true",
    )
    parser.add_argument("filename", help="filename", nargs=1, type=str, default=None)
    args = parser.parse_args()

    form = WinForm(args)
    form.show()

    sys.exit(app.exec_())
