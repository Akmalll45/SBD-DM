from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def format_idr(amount):
    return f'Rp {int(amount):,}'.replace(',', '.')


def render_invoice_pdf(order):
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f'Invoice Hendra Sport #{order.pk}',
        author='Hendra Sport',
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='InvoiceRight',
        parent=styles['Normal'],
        alignment=TA_RIGHT,
    ))
    styles.add(ParagraphStyle(
        name='InvoiceSmall',
        parent=styles['Normal'],
        fontSize=8,
        leading=11,
    ))

    safe_name = escape(order.full_name)
    safe_address = escape(order.address).replace('\n', '<br/>')
    elements = [
        Paragraph('HENDRA SPORT', styles['Title']),
        Paragraph(f'Invoice Pesanan #{order.pk}', styles['Heading2']),
        Paragraph(f'Tanggal: {order.created_at:%d-%m-%Y %H:%M}', styles['Normal']),
        Spacer(1, 8 * mm),
        Paragraph('<b>Penerima</b>', styles['Heading3']),
        Paragraph(
            f'{safe_name}<br/>{escape(order.phone)}<br/>'
            f'{safe_address}<br/>{escape(order.city)}',
            styles['Normal'],
        ),
        Spacer(1, 6 * mm),
    ]

    rows = [['Produk', 'Ukuran', 'Qty', 'Harga Satuan', 'Jumlah']]
    for item in order.items.all():
        product_label = escape(item.product_name)
        if item.has_sablon:
            product_label += (
                f'<br/><font size="7">Sablon: {escape(item.custom_name)} '
                f'#{item.custom_number if item.custom_number is not None else ""}</font>'
            )
        rows.append([
            Paragraph(product_label, styles['InvoiceSmall']),
            escape(item.size or '-'),
            str(item.quantity),
            format_idr(item.unit_price),
            format_idr(item.line_total),
        ])
    item_table = Table(rows, colWidths=[68 * mm, 18 * mm, 14 * mm, 32 * mm, 34 * mm], repeatRows=1)
    item_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#172554')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.extend([item_table, Spacer(1, 6 * mm)])

    payment = getattr(order, 'payment', None)
    payment_method = payment.get_method_display() if payment else 'Belum tersedia'
    payment_status = payment.get_status_display() if payment else 'Belum tersedia'
    summary = [
        ['Subtotal produk', format_idr(order.items_subtotal)],
        ['Ongkos kirim', format_idr(order.shipping_cost)],
        ['Total pembayaran', format_idr(order.total)],
        ['Metode pembayaran', payment_method],
        ['Status pembayaran', payment_status],
        ['Status pesanan', order.get_status_display()],
    ]
    summary_table = Table(summary, colWidths=[100 * mm, 66 * mm], hAlign='RIGHT')
    summary_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
        ('LINEABOVE', (0, 2), (-1, 2), 0.8, colors.HexColor('#172554')),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.extend([summary_table, Spacer(1, 10 * mm)])
    elements.append(Paragraph(
        'Simpan invoice ini sebagai bukti transaksi. Status pembayaran ditentukan oleh '
        'notifikasi resmi Midtrans atau verifikasi transfer oleh admin.',
        styles['InvoiceSmall'],
    ))
    document.build(elements)
    buffer.seek(0)
    return buffer
