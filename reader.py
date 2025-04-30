import zipfile

from PyQt5.QtWidgets import (
    QApplication, QWidget, QMenu, QAction, QPlainTextEdit,
    QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox, QColorDialog, QInputDialog
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QPoint
from PyQt5.QtGui import QTextCursor, QFont, QPalette, QColor, QCursor
import sys
from bs4 import BeautifulSoup


class MyTextEdit(QPlainTextEdit):
    """自定义 QPlainTextEdit，将鼠标和右键事件转发给父窗口。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        # 关闭默认菜单，使用父窗口菜单
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.parent.show_context_menu)

    def mousePressEvent(self, event):
        # 左键长按拖动由父窗口处理
        if event.button() == Qt.LeftButton:
            self.parent.mousePressEvent(event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 拖动事件
        self.parent.mouseMoveEvent(event)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # 结束拖动
        self.parent.mouseReleaseEvent(event)
        super().mouseReleaseEvent(event)


class SearchDialog(QDialog):
    positionSelected = pyqtSignal(int)

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("搜索")
        self.text = text
        self.resize(400, 300)

        layout = QVBoxLayout(self)
        self.input = QLineEdit(self)
        self.input.setPlaceholderText("输入关键词并回车")
        layout.addWidget(self.input)
        self.listWidget = QListWidget(self)
        layout.addWidget(self.listWidget)

        self.input.returnPressed.connect(self.perform_search)
        self.listWidget.itemClicked.connect(self.result_clicked)

    def perform_search(self):
        keyword = self.input.text().strip()
        self.listWidget.clear()
        if not keyword:
            return
        text = self.text
        length = len(text)
        start = 0
        ends = ['。', '！', '？', '.', '!', '?', '\n']
        while True:
            idx = text.find(keyword, start)
            if idx < 0:
                break
            # 当前句首尾
            sent_start = max(text.rfind(ch, 0, idx) for ch in ends)
            sent_start = sent_start+1 if sent_start >= 0 else 0
            sent_end_pos = min((pos for pos in (text.find(ch, idx+len(keyword)) for ch in ends) if pos >= 0), default=len(text))
            sent_end = sent_end_pos+1 if sent_end_pos < len(text) else len(text)
            # 前一句上下文
            prev_end = max((text.rfind(ch, 0, sent_start) for ch in ends), default=-1)
            prev_start = max((text.rfind(ch, 0, prev_end) for ch in ends), default=-1)+1 if prev_end>=0 else 0
            snippet = text[prev_start:sent_end]
            if prev_start>0:
                snippet = '...' + snippet
            if sent_end<len(text):
                snippet += '...'
            pct = idx/ max(length,1)*100
            item = QListWidgetItem(f"{snippet}   ({pct:.1f}%)")
            item.setData(Qt.UserRole, idx)
            self.listWidget.addItem(item)
            start = idx + len(keyword)

    def result_clicked(self, item):
        pos = item.data(Qt.UserRole)
        self.positionSelected.emit(pos)
        self.accept()


class NovelReader(QWidget):
    def __init__(self):
        super().__init__()
        # 无边框 & 背景透明
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("border: none;")

        # 置顶状态
        self._always_on_top = False
        # 拖动状态
        self._drag_active = False
        self._drag_enabled = False
        self._drag_pos = QPoint()

        # 窗口高度 & 初始大小
        self._default_height = 28
        self.setFixedHeight(self._default_height)
        self.resize(600, self._default_height)

        # 文本编辑区
        self.textEdit = MyTextEdit(self)
        self.textEdit.setReadOnly(True)
        self.textEdit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.textEdit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.textEdit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 默认背景和文字色
        pal = self.textEdit.palette()
        pal.setColor(QPalette.Base, QColor(0, 0, 0, 150))  # 半透明背景
        pal.setColor(QPalette.Text, QColor(255, 255, 255))
        self.textEdit.setPalette(pal)
        self.textEdit.setFont(QFont('Arial', 16))
        self.textEdit.setGeometry(0, 0, self.width(), self.height())
        # 定义过滤字符的字典
        self.filter_dict = {'<br />'}
        # 小说文本存储
        self.text = ''

    def resizeEvent(self, event):
        # 保持文本区跟随窗口大小
        self.textEdit.setGeometry(0, 0, self.width(), self.height())

    def show_context_menu(self, pos=None):
        global_pos = QCursor.pos()
        menu = QMenu()
        # 打开小说
        open_act = QAction('打开小说', self)
        open_act.triggered.connect(self.load_file)
        menu.addAction(open_act)
        # 设置窗口大小
        size_act = QAction('设置窗口大小', self)
        size_act.triggered.connect(self.set_window_size)
        menu.addAction(size_act)
        # 搜索
        search_act = QAction('搜索', self)
        search_act.triggered.connect(self.search)
        menu.addAction(search_act)
        # 置顶切换
        pin_text = '取消置顶' if self._always_on_top else '置顶'
        pin_act = QAction(pin_text, self)
        pin_act.triggered.connect(self.toggle_pin)
        menu.addAction(pin_act)
        # 背景色
        bg_act = QAction('设置背景色', self)
        bg_act.triggered.connect(self.set_bg_color)
        menu.addAction(bg_act)
        # 字体设置
        font_act = QAction('设置字体色/大小', self)
        font_act.triggered.connect(self.set_font)
        menu.addAction(font_act)

        # 跳转到百分比位置
        jump_act = QAction('跳转到百分比位置', self)
        jump_act.triggered.connect(self.jump_to_percentage)
        menu.addAction(jump_act)

        # 关闭页面
        close_act = QAction('关闭页面', self)
        close_act.triggered.connect(self.close)
        menu.addAction(close_act)
        menu.exec(global_pos)

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, '打开小说文件', 'D:\\书籍',
                                              'Text Files (*.txt);;EPUB Files (*.epub)')
        if not path:
            return
        try:
            if path.endswith('.txt'):
                with open(path, 'r', encoding='utf-8') as f:
                    self.text = f.read().replace('\r\n', '\n')
                    # 过滤无效空格和空白行
                    self.text = self.filter_whitespace(self.text)
            elif path.endswith('.epub'):
                try:
                    with zipfile.ZipFile(path, 'r') as zf:
                        text_content = ""
                        # 遍历所有 HTML 文件（EPUB 的内容通常在 OEBPS/content 目录下）
                        for name in zf.namelist():
                            if name.endswith('.xhtml') or name.endswith('.html'):
                                with zf.open(name) as f:
                                    content = f.read().decode('utf-8', errors='ignore')
                                    soup = BeautifulSoup(content, 'html.parser')
                                    text_content += soup.get_text() + "\n"
                        self.text = text_content
                        self.text = self.filter_whitespace(self.text)
                except Exception as e:
                    QMessageBox.warning(self, '错误', f'解析 EPUB 失败：{e}')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'无法读取文件：{e}')
            return
        self.textEdit.setPlainText(self.text)

        # 过滤空白行
    def filter_whitespace(self, text):
        lines = text.split('\n')
        # 过滤空白行
        non_empty_lines = [line.strip() for line in lines if line.strip()]
        # 过滤特定字符组合
        filtered_lines = []
        for line in non_empty_lines:
            for word in self.filter_dict:
                new_line = line.replace(word, '')
                filtered_lines.append(new_line)
            # 合并过滤后的行
        filtered_text = '\n'.join(filtered_lines)
        return filtered_text

    def set_window_size(self):
        # 设置宽度
        width, ok_w = QInputDialog.getInt(self, '窗口宽度', '输入窗口宽度：', self.width(), 100, 2000)
        if not ok_w:
            return
        # 设置高度
        height, ok_h = QInputDialog.getInt(self, '窗口高度', '输入窗口高度：', self._default_height, 30, 500)
        if not ok_h:
            return
        # 应用新尺寸
        self._default_height = height
        self.setFixedSize(width, height)
        # 更新文本区几何
        self.textEdit.setGeometry(0, 0, width, height)

    def search(self):
        if not self.text:
            QMessageBox.information(self, '提示', '请先打开小说文件')
            return
        dlg = SearchDialog(self.text, self)
        dlg.positionSelected.connect(self.jump_to)
        dlg.exec()

    def jump_to(self, idx):
        cursor = self.textEdit.textCursor()
        cursor.setPosition(idx)
        self.textEdit.setTextCursor(cursor)
        self.textEdit.ensureCursorVisible()

    def toggle_pin(self):
        self._always_on_top = not self._always_on_top
        flags = self.windowFlags()
        if self._always_on_top:
            self.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
        self.show()

    def set_bg_color(self):
        c = QColorDialog.getColor(parent=self)
        if c.isValid():
            pal = self.textEdit.palette()
            pal.setColor(QPalette.Base, c)
            self.textEdit.setPalette(pal)

    def set_font(self):
        # 字体色
        c = QColorDialog.getColor(parent=self)
        if c.isValid():
            pal = self.textEdit.palette()
            pal.setColor(QPalette.Text, c)
            self.textEdit.setPalette(pal)
        # 字号
        size, ok = QInputDialog.getInt(self, '字体大小', '输入字号：', self.textEdit.font().pointSize(), 6, 72)
        if ok:
            f = self.textEdit.font()
            f.setPointSize(size)
            self.textEdit.setFont(f)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            self._drag_active = True
            QTimer.singleShot(1000, lambda: setattr(self, '_drag_enabled', True))

    def mouseMoveEvent(self, event):
        if getattr(self, '_drag_enabled', False) and self._drag_active:
            self.move(event.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._drag_active = False
        self._drag_enabled = False

    def jump_to_percentage(self):
        if not self.text:
            QMessageBox.information(self, '提示', '请先打开小说文件')
            return
        percentage, ok = QInputDialog.getDouble(self, '跳转到百分比位置', '输入百分比（0 - 100）：', 0, 0, 100, 2)
        if ok:
            position = int(len(self.text) * percentage / 100)
            self.jump_to(position)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    reader = NovelReader()
    reader.show()
    sys.exit(app.exec_())