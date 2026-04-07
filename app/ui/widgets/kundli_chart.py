from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPen, QColor, QFont
from PyQt6.QtCore import Qt, QPointF

class KundliChart(QWidget):
    """A graphical widget to draw a North Indian style astrology chart."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 400)
        # Store dict mapping house int (1-12) to list of planet abbrevs (strings)
        self.house_data = {i: [] for i in range(1, 13)}

    def update_chart(self, raw_data_list):
        """
        Accepts list of charting dicts from HoroscopeService.
        Format expected: [{'Planet': 'Sun', 'House': 1, 'Sign': 'Aries', ...}, ...]
        """
        self.house_data = {i: [] for i in range(1, 13)}
        
        # Abbreviation mapping
        abbrevs = {
            "Sun": "Su", "Moon": "Mo", "Mars": "Ma", "Mercury": "Me",
            "Jupiter": "Ju", "Venus": "Ve", "Saturn": "Sa",
            "Rahu": "Ra", "Ketu": "Ke", "Ascendant": "As"
        }

        for item in raw_data_list:
            planet = item.get("Planet", "")
            house = int(item.get("House", 1))
            
            abbr = abbrevs.get(planet, planet[:2])
            if 1 <= house <= 12:
                self.house_data[house].append(abbr)
                
        self.update() # Triggers paintEvent

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        
        # Make the chart a square
        side = min(w, h) - 20
        offset_x = (w - side) / 2
        offset_y = (h - side) / 2

        # Setup Pen
        pen = QPen(QColor(50, 50, 50), 2)
        painter.setPen(pen)

        # Draw Outer Square
        painter.drawRect(int(offset_x), int(offset_y), int(side), int(side))

        # Draw Diagonals
        painter.drawLine(int(offset_x), int(offset_y), int(offset_x + side), int(offset_y + side))
        painter.drawLine(int(offset_x + side), int(offset_y), int(offset_x), int(offset_y + side))

        # Draw Inner Diamond connecting midpoints
        # Midpoints
        top_mid = QPointF(offset_x + side / 2, offset_y)
        right_mid = QPointF(offset_x + side, offset_y + side / 2)
        bottom_mid = QPointF(offset_x + side / 2, offset_y + side)
        left_mid = QPointF(offset_x, offset_y + side / 2)

        painter.drawLine(top_mid, right_mid)
        painter.drawLine(right_mid, bottom_mid)
        painter.drawLine(bottom_mid, left_mid)
        painter.drawLine(left_mid, top_mid)

        # Plot planets
        self._plot_planets(painter, offset_x, offset_y, side)

    def _plot_planets(self, painter: QPainter, ox: float, oy: float, side: float):
        """Draws the text of the planets into the respective house coordinates."""
        painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        
        # House centers (Relative percentages X, Y)
        # Mapped mathematically to land nicely inside the geometric areas
        centers = {
            1: (0.5, 0.25),
            2: (0.25, 0.15),
            3: (0.15, 0.25),
            4: (0.25, 0.5),
            5: (0.15, 0.75),
            6: (0.25, 0.85),
            7: (0.5, 0.75),
            8: (0.75, 0.85),
            9: (0.85, 0.75),
            10: (0.75, 0.5),
            11: (0.85, 0.25),
            12: (0.75, 0.15)
        }

        for house_num, planet_list in self.house_data.items():
            if not planet_list:
                continue
                
            rx, ry = centers.get(house_num, (0.5, 0.5))
            cx = ox + side * rx
            cy = oy + side * ry
            
            # Create a combined string e.g. "Su Mo Ma"
            text = " ".join(planet_list)
            
            # Ensure text is centered around cx, cy
            font_metrics = painter.fontMetrics()
            tw = font_metrics.horizontalAdvance(text)
            th = font_metrics.height()
            
            painter.drawText(int(cx - tw / 2), int(cy + th / 4), text)
