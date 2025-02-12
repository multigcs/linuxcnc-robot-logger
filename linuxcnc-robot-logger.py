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
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSlider,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

MODE_NAMES = ["WORLD", "JOINT"]
AXIS_NAMES = ["X", "Y", "Z", "A", "B", "C", "U", "V", "W"]
TYPE_NAMES = ["WORLD", "JOINT", "SEC", "MS", "ON", "OFF", "CW", "CCW", "STOP"]
COMMAND_NAMES = ["MOVE", "PAUSE", "AIO", "DIO", "SPINDLE", "MARKER"]

# http://linuxcnc.org/docs/master/html/de/config/python-interface.html
s = linuxcnc.stat()
c = linuxcnc.command()


loglist = []



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

        self.logtable = QTableWidget()
        self.logtable.setColumnCount(11)

        self.logtable.setHorizontalHeaderItem(0, QTableWidgetItem("CTRL"))
        self.logtable.setHorizontalHeaderItem(1, QTableWidgetItem("Command"))
        self.logtable.setHorizontalHeaderItem(2, QTableWidgetItem("Type"))
        for axis_num, axis in enumerate(AXIS_NAMES):
            self.logtable.setHorizontalHeaderItem(axis_num + 3, QTableWidgetItem(f"{axis_num} ({axis})"))
        self.logtable.setHorizontalHeaderItem(9, QTableWidgetItem("Speed"))
        self.logtable.setHorizontalHeaderItem(10, QTableWidgetItem("Comment"))
        self.logtable.setFixedWidth(1400)

        self.logtable.itemChanged.connect(self.logtable_load)

        layoutMain.addWidget(self.logtable)

        self.logview = QPlainTextEdit()
        self.logview.setFixedWidth(450)
        #layoutMain.addWidget(self.logview)
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
            if an < 6:
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


        self.j0pos = QSlider(Qt.Horizontal)
        self.j0pos.setFixedWidth(250)
        self.j0pos.setMinimum(-1800)
        self.j0pos.setMaximum(1800)
        self.j0pos.setSingleStep(1)
        
        self.j0pos_active = True
        self.j0pos_last = True
        
        def slide_stop():
            print("stop update")
            self.j0pos_active = False
            self.j0pos_last = self.j0pos.value()

        def slide_start():
            print("start update")
            self.j0pos_active = True

        def slide_move(pos):
            print("slider.j0.counts", int((pos - self.j0pos_last) / 10.0))
            self.j0pos_last = pos

        self.j0pos.sliderPressed.connect(slide_stop)
        self.j0pos.sliderReleased.connect(slide_start)
        self.j0pos.sliderMoved.connect(slide_move)
        
        layoutleft.addWidget(self.j0pos)

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


    def loglist_row_by_widget(self, widget):
        for num in range(self.logtable.rowCount()):
            if widget == self.logtable.cellWidget(num, 0):
                return num
        return -1

    def loglist_del(self, widget):
        row_n = self.loglist_row_by_widget(widget)
        if row_n >= 0:
            model = self.logtable.model()
            idx = self.logtable.model().index(row_n, 0)
            model.removeRow(idx.row()) 

    def loglist_up(self, widget):
        row_n = self.loglist_row_by_widget(widget)
        if row_n != 0:
            urow = self.logtable_row(row_n - 1)
            row = self.logtable_row(row_n)
            self.loglist_add(row, row_n - 1)
            self.loglist_add(urow, row_n)

    def loglist_insert(self, widget):
        row_n = self.loglist_row_by_widget(widget)
        self.logtable.insertRow(row_n + 1)

        # clone
        #row = self.logtable_row(row_n)
        # insert marker
        row = ["MARKER", ""]

        self.loglist_add(row, row_n + 1)

    def loglist_row_by_marker(self):
        for row_n in range(self.logtable.rowCount()):
            row = self.logtable_row(row_n)
            print(row)
            if row[0] == "MARKER":
                return row_n
        return -1


    def loglist_add(self, row, row_n=-1):
        if row_n == -1:
            # find marker
            row_n = self.loglist_row_by_marker()
            if row_n != -1:
                self.logtable.insertRow(row_n)
            else:
                # add row
                row_n = self.logtable.rowCount()
                self.logtable.setRowCount(row_n + 1)
            
        buttons_layout = QHBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_widget = QWidget()
        buttons_widget.setLayout(buttons_layout)
        button1 = QPushButton("^")
        button1.clicked.connect(partial(self.loglist_up, buttons_widget))
        buttons_layout.addWidget(button1)
        button2 = QPushButton("-")
        button2.clicked.connect(partial(self.loglist_del, buttons_widget))
        buttons_layout.addWidget(button2)
        button3 = QPushButton("+")
        button3.clicked.connect(partial(self.loglist_insert, buttons_widget))
        buttons_layout.addWidget(button3)
        self.logtable.setCellWidget(row_n, 0, buttons_widget)
        for col_n, col in enumerate(row):
            value = f"{col}"
            if col_n == 0:
                combo = QComboBox()
                combo.setEditable(True)
                for command_n, command in enumerate([""] + COMMAND_NAMES):
                    combo.addItem(command)
                    if command == value:
                        combo.setCurrentIndex(command_n)
                combo.editTextChanged.connect(self.logtable_load)
                self.logtable.setCellWidget(row_n, col_n + 1, combo)
            elif col_n == 1:
                combo = QComboBox()
                combo.setEditable(True)
                tlist = [""] + TYPE_NAMES
                if value not in tlist:
                    tlist.append(value)
                for command_n, command in enumerate(tlist):
                    combo.addItem(command)
                    if command == value:
                        combo.setCurrentIndex(command_n)
                combo.editTextChanged.connect(self.logtable_load)
                self.logtable.setCellWidget(row_n, col_n + 1, combo)
            else:
                self.logtable.setItem(row_n, col_n + 1, QTableWidgetItem(value)) 


    def logtable_row(self, row_n):
        row = []
        row.append(self.logtable.cellWidget(row_n, 1).currentText())
        row.append(self.logtable.cellWidget(row_n, 2).currentText())
        for col_n in range(8):
            row.append(self.logtable.model().data(self.logtable.model().index(row_n, col_n + 3)))
        return row

    def logtable_load(self):
        print("(robot-logger)")
        last_mode = ""
        for row_n in range(self.logtable.rowCount()):
            row = self.logtable_row(row_n)
            command = row[0]
            ctype = row[1]
            values = row[2:]

            comment = values[7]
            if command == "MOVE":
                speed = values[6]
                if ctype != last_mode:
                    if ctype == "WORLD":
                        print("M428 (WORLD COORDS)")
                    else:
                        print("M429 (JOINT COORDS)")
                    last_mode = ctype
                if not comment:
                    comment = "move to"
                positions = []
                for axis_num in range(6):
                    value = values[axis_num]
                    axis_name = AXIS_NAMES[axis_num]
                    positions.append(f"{axis_name}{value}")
                if speed:
                    speed = int(speed)
                if speed:
                    print(f"G01 {' '.join(positions)} ({comment})")
                else:
                    print(f"G00 {' '.join(positions)} ({comment})")

            elif command == "PAUSE":
                sec = int(values[0] or 0)
                if ctype == "MS":
                    sec /= 1000
                if not comment:
                    comment = "pause"
                print(f"G4 P{sec} ({comment})")

            elif command == "AIO":
                ch = values[0]
                value = values[1]
                if not comment:
                    comment = "analog-out"
                print(f"M68 E{ch} Q{value} ({comment})")

            elif command == "DIO":
                ch = values[0]
                if ctype == "ON":
                    if not comment:
                        comment = "digital-out on"
                    print(f"M64 P{ch} ({comment})")
                elif ctype == "OFF":
                    if not comment:
                        comment = "digital-out off"
                    print(f"M65 P{ch} ({comment})")

            elif command == "SPINDLE":
                speed = values[6]
                if ctype == "CW":
                    if not comment:
                        comment = "spindle on CW"
                    print(f"M03 S{speed} ({comment})")
                elif ctype == "CCW":
                    if not comment:
                        comment = "spindle on CCW"
                    print(f"M04 S{speed} ({comment})")
                else:
                    if not comment:
                        comment = "spindle off"
                    print(f"M05 ({comment})")

        print("M02")



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

        self.spindle = s.spindle[0]

        # get joint positions
        # need to update this offsets in Joint-Mode, not available in World-Mode :(
        offsets_g5x = (0.0, -90.0, 0.0, 0.0, 90.0, 0.0, 0.0, 0.0, 0.0)
        for n, pos in enumerate(s.joint_position):
            if n >= len(s.axis):
                break

            if n == 0 and self.j0pos_active:
                self.j0pos.setValue(int(pos * 10))


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


    def reset_callback(self):
        self.pulse = " "
        self.mode = None
        self.spindle = {"enabled": 0}
        self.last_mode = None
        self.pos_w = [None] * 9
        self.pos_ws = [False] * 9
        self.pos_wr = [None] * 9
        self.last_pos_w = [None] * 9
        self.pos_j = [None] * 9
        self.last_pos_j = [None] * 9
        self.last_aout = [0.0] * 64
        self.last_dout = [0] * 64
        self.last_spindle = {}
        self.logview.clear()

        gcode = ""
        if os.path.isfile(args.filename[0]):
            # loading gcode from existing file
            gcode = open(args.filename[0], "r").read()
        if gcode:
            # remove programm end (M02)
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
        self.loglist_add(["PAUSE", "S", 1, 0, 0, 0, 0, 0, 0, "pause for 1s"])
        self.logtable_load()



    def add_callback(self):
        self.statusUpdate()

        do_move = False

        # check coords mode (world/joint)
        mode = 0.0
        if not args.joints:
            mode = s.aout[3]
            if mode != self.last_mode:
                self.last_mode = mode

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
                        do_move = True
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
                        do_move = True
                        self.last_pos_w[n] = position

        # analog outputs
        do_pause = 0
        for n, value in enumerate(s.aout):
            if n == 3:
                # in robot mode, we can read the kinstype here
                continue
            if value != self.last_aout[n]:
                self.last_aout[n] = value
                self.loglist_add(["AIO", "SET", f"{n}", f"{value}", "", "", "", "", "", "set analog"])
                do_pause = max(do_pause, 500)


        # digital outputs
        for n, value in enumerate(s.dout):
            if n == 3:
                # in robot mode, we can read the kinstype here
                continue
            if value != self.last_dout[n]:
                self.last_dout[n] = value
                if value == 1:
                    self.loglist_add(["DIO", "ON", f"{n}", "", "", "", "", "", "", "set digital"])
                else:
                    self.loglist_add(["DIO", "OFF", f"{n}", "", "", "", "", "", "", "set digital"])
                do_pause = max(do_pause, 100)

        # spindle
        if self.spindle != self.last_spindle:
            self.last_spindle = self.spindle
            if self.spindle["enabled"]:
                if self.spindle["direction"]:
                    self.loglist_add(["SPINDLE", "CW", "", "", "", "", "", "", self.spindle["speed"], "set spindle"])
                else:
                    self.loglist_add(["SPINDLE", "CCW", "", "", "", "", "", "", self.spindle["speed"], "set spindle"])
            else:
                self.loglist_add(["SPINDLE", "STOP", "", "", "", "", "", "", "", "set spindle"])
            do_pause = max(do_pause, 500)

        if do_pause:
            self.loglist_add(["PAUSE", "MS", do_pause, 0, 0, 0, 0, 0, "", f"pause for {do_pause}ms"])


        if do_move:
            logentry = []
            mode = s.aout[3]
            if mode == 0:
                logentry.append("MOVE")
                logentry.append("WORLD")
                for pos_n in range(6):
                    logentry.append(self.pos_w[pos_n])
                logentry.append("500")
                logentry.append("move axis to")
            else:
                logentry.append("MOVE")
                logentry.append("JOINT")
                for pos_n in range(6):
                    logentry.append(self.pos_j[pos_n])
                logentry.append("500")
                logentry.append("move joints to")
            self.loglist_add(logentry)

        self.logtable_load()

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
