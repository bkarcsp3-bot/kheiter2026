def _shape_ar(text):
    s = str(text or "")
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(s))
    except Exception:
        return s


def _render_admin_pdf_response(title, subtitle, cards, headers, rows, ascii_name, arabic_name, footer_note=""):
    from urllib.parse import quote
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 1) المحاولة الأولى: WeasyPrint (إن كانت مثبتة وتعمل بدون أخطاء)
    try:
        from weasyprint import HTML
        card_blocks = []
        for item in cards:
            sub_part = f'<div class="sub">{item["sub"]}</div>' if item.get("sub") else ""
            card_blocks.append(
                f'<div class="card"><div class="lbl">{item["label"]}</div><div class="val">{item["val"]}</div>{sub_part}</div>'
            )
        cards_html = "".join(card_blocks)
        ths_html = "".join(f"<th>{h}</th>" for h in headers)
        trs_html = "".join(
            "<tr>" + "".join(f"<td>{col}</td>" for col in r) + "</tr>"
            for r in rows
        )
        note_html = f'<div class="note">{footer_note}</div>' if footer_note else ""
        html_doc = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<style>
  @page {{ size: A4 landscape; margin: 10mm; }}
  body {{ font-family: 'DejaVu Sans', 'Arial', sans-serif; direction: rtl; color: #0f172a; margin: 0; font-size: 9.5pt; }}
  .top {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 3px solid #c5963a; padding-bottom: 6px; margin-bottom: 10px; }}
  .top h2 {{ margin: 0; font-size: 14pt; color: #0f2942; }}
  .top p {{ margin: 2px 0 0; font-size: 8.5pt; color: #475569; }}
  .meta {{ text-align: left; font-size: 8pt; color: #334155; }}
  .cards {{ display: flex; gap: 6px; margin-bottom: 10px; }}
  .card {{ flex: 1; border: 1px solid #cbd5e1; border-top: 3px solid #0f2942; border-radius: 5px; padding: 6px; background: #f8fafc; text-align: center; }}
  .card .lbl {{ font-size: 7.8pt; color: #475569; font-weight: bold; }}
  .card .val {{ font-size: 12pt; color: #0f2942; font-weight: bold; margin-top: 2px; }}
  .card .sub {{ font-size: 7.5pt; color: #047857; font-weight: bold; margin-top: 2px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 8.2pt; }}
  th {{ background: #0f2942; color: #ffffff; padding: 5px 4px; border: 1px solid #1e3a5f; text-align: center; }}
  td {{ padding: 4px; border: 1px solid #cbd5e1; text-align: center; }}
  tr:nth-child(even) {{ background: #f8fafc; }}
  .note {{ margin-top: 8px; padding: 6px 8px; background: #fffbeb; border: 1px solid #fcd34d; border-radius: 5px; font-size: 8pt; color: #78350f; }}
  .foot {{ margin-top: 8px; padding-top: 5px; border-top: 1px solid #e2e8f0; text-align: center; font-size: 7.8pt; color: #64748b; }}
</style>
</head>
<body>
  <div class="top">
    <div><h2>{title}</h2><p>{subtitle}</p></div>
    <div class="meta"><div><strong>الهيئة:</strong> بلدية الخيثر</div><div><strong>الوقت:</strong> {now_str}</div></div>
  </div>
  <div class="cards">{cards_html}</div>
  <table><thead><tr>{ths_html}</tr></thead><tbody>{trs_html}</tbody></table>
  {note_html}
  <div class="foot">السلطة الوطنية المستقلة للانتخابات — بلدية الخيثر • 28 نوفمبر 2026</div>
</body>
</html>"""
        pdf_bytes = HTML(string=html_doc).write_pdf()
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f"inline; filename={ascii_name}; filename*=UTF-8''{quote(arabic_name)}"},
        )
    except Exception:
        pass

    # 2) المحاولة الثانية: ReportLab مع تسجيل خط عربي إذا توفر
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfgen import canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        font_name = "Helvetica"
        font_candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
        ]
        for fpath in font_candidates:
            if os.path.exists(fpath):
                pdfmetrics.registerFont(TTFont("ArFont", fpath))
                font_name = "ArFont"
                break

        buf = io.BytesIO()
        page_w, page_h = landscape(A4)
        c = canvas.Canvas(buf, pagesize=landscape(A4))
        c.setTitle(ascii_name)

        y = page_h - 32
        c.setFont(font_name, 13)
        c.drawRightString(page_w - 30, y, _shape_ar(title))
        c.setFont(font_name, 8.5)
        c.drawString(30, y, _shape_ar(f"التاريخ: {now_str}"))
        y -= 16
        c.drawRightString(page_w - 30, y, _shape_ar(subtitle))

        y -= 24
        if cards:
            card_w = (page_w - 60 - (len(cards) - 1) * 8) / len(cards)
            for idx, item in enumerate(cards):
                x = 30 + idx * (card_w + 8)
                c.rect(x, y - 34, card_w, 34, stroke=1, fill=0)
                c.setFont(font_name, 8)
                c.drawCentredString(x + card_w / 2, y - 12, _shape_ar(item["label"]))
                c.setFont(font_name, 10)
                c.drawCentredString(x + card_w / 2, y - 26, _shape_ar(str(item["val"])))
            y -= 48

        cols_count = max(len(headers), 1)
        col_w = (page_w - 60) / cols_count
        c.setFont(font_name, 7.5)
        for i, h_txt in enumerate(headers):
            c.rect(30 + i * col_w, y - 18, col_w, 18, stroke=1, fill=0)
            c.drawCentredString(30 + (i + 0.5) * col_w, y - 12, _shape_ar(h_txt))
        y -= 18

        for r in rows:
            if y < 40:
                c.showPage()
                y = page_h - 40
                c.setFont(font_name, 7.5)
            for i in range(cols_count):
                val = r[i] if i < len(r) else ""
                c.rect(30 + i * col_w, y - 16, col_w, 16, stroke=1, fill=0)
                c.drawCentredString(30 + (i + 0.5) * col_w, y - 11, _shape_ar(str(val)))
            y -= 16

        c.save()
        return Response(
            buf.getvalue(),
            mimetype="application/pdf",
            headers={"Content-Disposition": f"inline; filename={ascii_name}; filename*=UTF-8''{quote(arabic_name)}"},
        )
    except Exception:
        pass

    # 3) خطة أمان أخيرة (HTML للطباعة المباشرة عبر المتصفح دون خطأ 500)
    ths_html = "".join(f"<th>{h}</th>" for h in headers)
    trs_html = "".join("<tr>" + "".join(f"<td>{col}</td>" for col in r) + "</tr>" for r in rows)
    fallback_html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl"><head><meta charset="UTF-8">
<style>body{{font-family:Tahoma,Arial,sans-serif;direction:rtl;padding:16px}}table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #999;padding:6px;text-align:center}}</style>
</head><body onload="window.print()">
<h3>{title}</h3><p>{subtitle} — {now_str}</p>
<table><thead><tr>{ths_html}</tr></thead><tbody>{trs_html}</tbody></table>
</body></html>"""
    return Response(fallback_html, mimetype="text/html; charset=utf-8")