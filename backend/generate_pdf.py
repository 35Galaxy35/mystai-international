import os
import uuid
from fpdf import FPDF
from PIL import Image

# Konumlar
BASE_DIR = os.path.dirname(__file__)
FONT_PATH_TTF = os.path.join(BASE_DIR, "fonts", "DejaVuSans.ttf")
LOGO_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "images", "mystai-logo.png"))

# PDF sınıfı (logo + header + footer)
class MystPDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Unicode font ekle
        if os.path.exists(FONT_PATH_TTF):
            self.add_font("DejaVu", "", FONT_PATH_TTF, uni=True)
            self.add_font("DejaVu", "B", FONT_PATH_TTF, uni=True)

    def header(self):
        if LOGO_PATH and os.path.exists(LOGO_PATH):
            self.image(LOGO_PATH, 12, 8, 22)

        self.set_xy(40, 9)
        self.set_font("DejaVu", "B", 12)
        self.set_text_color(25, 30, 55)
        self.cell(0, 6, "MystAI Astrology", ln=1)

        self.set_xy(40, 15)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(110, 115, 150)
        self.cell(0, 4, "mystai.ai • AI-powered divination & astrology", ln=1)

        self.ln(6)
        self.set_text_color(25, 25, 40)

    def footer(self):
        self.set_y(-13)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(130, 130, 160)
        self.cell(0, 8, f"MystAI.ai • Page {self.page_no()}", align="C")


# ========== PDF ÜRETME FONKSİYONU ==========
def generate_pdf_file(
    text: str,
    lang: str = "en",
    report_type: str = "natal",
    chart_id: str = None,
    birth_date: str = None,
    birth_time: str = None,
    birth_place: str = None,
    name: str = None,
):
    """
    Tek başına PDF üretir ve path döner.
    Harita varsa /tmp/<chart_id>.png okunur.
    """
    pdf_id = uuid.uuid4().hex
    pdf_path = f"/tmp/{pdf_id}.pdf"

    # Dil doğrulama
    if lang not in ("tr", "en"):
        lang = "en"

    # report_type doğrulama
    if report_type not in ("natal", "solar", "transits"):
        report_type = "natal"

    pdf = MystPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.alias_nb_pages()
    pdf.add_page()

    # ========== BAŞLIKLAR ==========
    if lang == "tr":
        if report_type == "solar":
            title = "MystAI Güneş Dönüşü Astroloji Raporu"
            sub = (
                "Bu rapor, doğum haritan ile güneş dönüşü haritanı bir araya getirerek "
                "yaklaşık bir yıllık ana temaları özetler."
            )
        elif report_type == "transits":
            title = "MystAI Transit Astroloji Raporu"
            sub = "Bu rapor güncel gezegen hareketlerini doğum haritanla ilişkilendirir."
        else:
            title = "MystAI Natal Doğum Haritası Raporu"
            sub = "Bu rapor kişilik, yaşam amacı, ilişkiler ve ruhsal yapı hakkında içgörü sunar."

        intro = "Detaylı astroloji raporun aşağıdadır:"
    else:
        if report_type == "solar":
            title = "MystAI Solar Return Astrology Report"
            sub = "Your annual solar return chart interpreted for themes and lessons."
        elif report_type == "transits":
            title = "MystAI Transit Astrology Report"
            sub = "Current planetary movements interpreted against your natal chart."
        else:
            title = "MystAI Natal Astrology Report"
            sub = "Your natal chart interpreted for personality, relationships and destiny."

        intro = "Your detailed astrology report is below:"

    # Başlık
    pdf.set_font("DejaVu", "B", 17)
    pdf.set_text_color(30, 32, 60)
    pdf.multi_cell(0, 8, title)
    pdf.ln(2)

    pdf.set_font("DejaVu", "", 11)
    pdf.set_text_color(85, 90, 125)
    pdf.multi_cell(0, 6, sub)
    pdf.ln(6)

    # Meta satırları
    meta = []
    if birth_date and birth_time and birth_place:
        if lang == "tr":
            meta.append(f"Doğum: {birth_date} • {birth_time} • {birth_place}")
        else:
            meta.append(f"Birth: {birth_date} • {birth_time} • {birth_place}")

    if name:
        meta.append(f"{'Danışan' if lang=='tr' else 'Client'}: {name}")

    if meta:
        pdf.set_font("DejaVu", "", 9)
        pdf.set_text_color(105, 110, 140)
        pdf.multi_cell(0, 4.5, "  •  ".join(meta))
        pdf.ln(5)

    # ========== HARİTA ==========
    if chart_id and report_type in ("natal", "solar"):
        chart_path = f"/tmp/{chart_id}.png"
        if os.path.exists(chart_path):
            img = Image.open(chart_path).convert("RGB")
            temp_jpg = f"/tmp/{chart_id}_rgb.jpg"
            img.save(temp_jpg, "JPEG", quality=95)

            img_width = 140
            x = (210 - img_width) / 2
            y = pdf.get_y() + 4

            pdf.image(temp_jpg, x=x, y=y, w=img_width)
            pdf.add_page()

    # ========== METİN ==========
    pdf.set_font("DejaVu", "B", 13)
    pdf.set_text_color(35, 35, 55)
    pdf.multi_cell(0, 7, intro)
    pdf.ln(3)

    pdf.set_font("DejaVu", "", 11)
    pdf.set_text_color(25, 25, 40)

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            pdf.ln(2)
            continue
        pdf.multi_cell(0, 5.5, line)
        pdf.ln(0.5)

    pdf.output(pdf_path)
    return pdf_path
