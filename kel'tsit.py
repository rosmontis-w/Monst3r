# @Version  :1.0
# @Author   :only073
# @Time     :2026/9/19  15:08
# @Project  :Honey Cakes
# @File     :kel'tsit.py

import sys
import json
import uuid
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QLabel, QDialog, QLineEdit,
    QTableWidget, QTableWidgetItem, QDialogButtonBox,
    QMessageBox, QSplitter
)
from PySide6.QtCore import Qt

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

# 中文显示
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

# 数据文件位置：打包后放在 exe 旁边
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "pie_data.json"


class PieCanvas(FigureCanvasQTAgg):
    """画饼图的画布"""
    def __init__(self):
        fig = Figure(figsize=(5, 4), dpi=100)
        super().__init__(fig)
        self.ax = fig.add_subplot(111)

    def draw_pie(self, title, items):
        self.ax.clear()
        labels = [it["label"] for it in items]
        values = [it["value"] for it in items]
        if not values or sum(values) <= 0:
            self.ax.text(0.5, 0.5, "暂无数据", ha='center', va='center', fontsize=14)
            self.ax.axis('off')
        else:
            self.ax.pie(values, labels=labels, autopct='%1.1f%%', startangle=90)
            self.ax.axis('equal')
        self.ax.set_title(title or "未命名", fontsize=14)
        self.draw()

    def draw_empty(self, text="点击左侧“新建”添加饼图"):
        self.ax.clear()
        self.ax.text(0.5, 0.5, text, ha='center', va='center', fontsize=12, color='gray')
        self.ax.axis('off')
        self.draw()


class EditDialog(QDialog):
    """新建 / 编辑 对话框"""
    def __init__(self, config=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑饼图")
        self.resize(420, 420)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("标题："))
        self.title_edit = QLineEdit()
        layout.addWidget(self.title_edit)

        layout.addWidget(QLabel("数据项（名称 / 数值）："))
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["名称", "数值"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 180)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("添加一行")
        del_btn = QPushButton("删除选中行")
        add_btn.clicked.connect(lambda: self.add_row())
        del_btn.clicked.connect(self.del_row)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("确定")
        buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if config:
            self.title_edit.setText(config.get("title", ""))
            for it in config.get("items", []):
                self.add_row(it["label"], it["value"])
        else:
            self.add_row("项目A", 30)
            self.add_row("项目B", 70)

    def add_row(self, label="", value=""):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem(str(label)))
        self.table.setItem(r, 1, QTableWidgetItem(str(value)))

    def del_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)

    def get_config(self):
        title = self.title_edit.text().strip()
        items = []
        for r in range(self.table.rowCount()):
            l_item = self.table.item(r, 0)
            v_item = self.table.item(r, 1)
            label = l_item.text().strip() if l_item else ""
            vtext = v_item.text().strip() if v_item else ""
            if not label:
                continue
            try:
                value = float(vtext)
            except ValueError:
                value = 0
            items.append({"label": label, "value": value})
        return {"title": title, "items": items}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("饼图记录工具")
        self.resize(960, 640)

        self.configs = []

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        # 左侧
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel("图表列表"))
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self.on_select)
        left_layout.addWidget(self.list_widget)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("新建")
        self.edit_btn = QPushButton("编辑")
        self.del_btn = QPushButton("删除")
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.del_btn)
        left_layout.addLayout(btn_row)

        splitter.addWidget(left)

        # 右侧
        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.canvas = PieCanvas()
        right_layout.addWidget(self.canvas)
        splitter.addWidget(right)
        splitter.setSizes([260, 700])

        self.add_btn.clicked.connect(self.add_chart)
        self.edit_btn.clicked.connect(self.edit_chart)
        self.del_btn.clicked.connect(self.delete_chart)

        self.load_data()
        self.refresh_list()

    # ---------- 数据持久化 ----------
    def load_data(self):
        if DATA_FILE.exists():
            try:
                self.configs = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            except Exception:
                self.configs = []

    def save_data(self):
        DATA_FILE.write_text(
            json.dumps(self.configs, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    # ---------- 列表 ----------
    def refresh_list(self):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        for c in self.configs:
            self.list_widget.addItem(c.get("title") or "未命名")
        self.list_widget.blockSignals(False)

        if self.configs:
            self.list_widget.setCurrentRow(0)
        else:
            self.canvas.draw_empty()

    def on_select(self, row):
        if 0 <= row < len(self.configs):
            c = self.configs[row]
            self.canvas.draw_pie(c.get("title", ""), c.get("items", []))

    # ---------- 增删改 ----------
    def add_chart(self):
        dlg = EditDialog(parent=self)
        if dlg.exec():
            cfg = dlg.get_config()
            cfg["id"] = str(uuid.uuid4())
            self.configs.append(cfg)
            self.save_data()
            self.refresh_list()
            self.list_widget.setCurrentRow(len(self.configs) - 1)

    def edit_chart(self):
        row = self.list_widget.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一个图表")
            return
        dlg = EditDialog(self.configs[row], self)
        if dlg.exec():
            cfg = dlg.get_config()
            cfg["id"] = self.configs[row].get("id", str(uuid.uuid4()))
            self.configs[row] = cfg
            self.save_data()
            self.refresh_list()
            self.list_widget.setCurrentRow(row)

    def delete_chart(self):
        row = self.list_widget.currentRow()
        if row < 0:
            return
        if QMessageBox.question(self, "确认", "确定删除这个图表吗？") == QMessageBox.Yes:
            self.configs.pop(row)
            self.save_data()
            self.refresh_list()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())