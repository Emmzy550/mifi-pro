
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
from models.organization import Organization
from models.payment import Payment, PaymentStatus
from pricing_config import PLAN_CONFIG

class InvoiceAgent:
    """
    Generates professional PDF invoices for organization upgrades.
    Uses reportlab for layout and branding.
    """
    
    INVOICE_DIR = "invoices"

    @staticmethod
    def generate_invoice_pdf(org: Organization, payment: Payment) -> str:
        """
        Creates a PDF invoice for a specific payment and returns the local file path.
        """
        os.makedirs(InvoiceAgent.INVOICE_DIR, exist_ok=True)
        
        filename = f"Invoice_{payment.payment_id}_{payment.invoice_id or payment.reference_code}.pdf"
        file_path = os.path.join(InvoiceAgent.INVOICE_DIR, filename)
        
        plan_info = PLAN_CONFIG.get(payment.plan.upper(), {})
        plan_display_name = plan_info.get("name", payment.plan)

        doc = SimpleDocTemplate(
            file_path,
            pagesize=letter,
            leftMargin=0.75*inch,
            rightMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        styles = getSampleStyleSheet()
        accent_color = colors.Color(0.07, 0.1, 0.15) # Deeper Navy #111827
        subtle_grey = colors.Color(0.93, 0.94, 0.96)

        def fmt_amount(value: float) -> str:
            return f"{payment.currency} {value:,.2f}"

        issue_date = payment.timestamp
        due_date = issue_date + timedelta(days=7)
        
        # Define Styles
        title_style = ParagraphStyle(
            'InvoiceTitle',
            parent=styles['Title'],
            fontSize=30,
            fontName='Helvetica-Bold',
            textColor=accent_color,
            alignment=0,
            leading=40,
            spaceAfter=0
        )
        
        sub_title_style = ParagraphStyle(
            'InvoiceSubTitle',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.grey,
            fontName='Helvetica-Oblique',
            leading=12,
            spaceAfter=20
        )
        
        section_header_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading2'],
            fontSize=11,
            fontName='Helvetica-Bold',
            textColor=accent_color,
            textTransform='UPPERCASE',
            letterSpacing=1.5,
            spaceBefore=0,
            spaceAfter=6
        )
        
        label_style = ParagraphStyle(
            'Label',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            textTransform='UPPERCASE',
            letterSpacing=0.5
        )
        
        value_style = ParagraphStyle(
            'Value',
            parent=styles['Normal'],
            fontSize=11,
            fontName='Helvetica-Bold'
        )

        content = []
        content.append(Spacer(1, 10))
        
        # 1. Header (Branding)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logo_path = os.path.join(base_dir, "frontend", "public", "logo.png")
        logo_cell = None
        if os.path.exists(logo_path):
            try:
                logo_img = Image(logo_path, width=0.6*inch, height=0.6*inch)
                logo_img.hAlign = 'LEFT'
                logo_cell = logo_img
            except Exception:
                logo_cell = None

        brand_block = [Paragraph("Mifi-Pro", title_style), Paragraph("Enterprise Credit Intelligence", sub_title_style)]
        if logo_cell:
            branding_left = Table([[logo_cell, brand_block]], colWidths=[0.8*inch, 3.4*inch])
            branding_left.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
        else:
            branding_left = brand_block

        branding_data = [[branding_left,
                          Paragraph("INVOICE", ParagraphStyle('RightTitle', parent=styles['Title'], fontSize=24, alignment=2, textColor=colors.lightgrey, fontName='Helvetica-Bold'))]]
        branding_table = Table(branding_data, colWidths=[4.2*inch, 2.8*inch])
        branding_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'BOTTOM')]))
        content.append(branding_table)
        content.append(HRFlowable(width="100%", thickness=1.5, color=accent_color, spaceAfter=20))
        
        # 2. Invoice Meta Details (ID, Date, Due, Status)
        status_color = colors.green if payment.status == PaymentStatus.PAID else colors.orange
        due_label = "Paid Date" if payment.status == PaymentStatus.PAID else "Due Date"
        due_value = issue_date.strftime("%b %d, %Y") if payment.status == PaymentStatus.PAID else due_date.strftime("%b %d, %Y")
        meta_data = [
            [Paragraph("Invoice Number", label_style), Paragraph("Issue Date", label_style), Paragraph(due_label, label_style), Paragraph("Payment Status", label_style)],
            [
                Paragraph(payment.invoice_id or payment.reference_code or "INV-PENDING", value_style),
                Paragraph(issue_date.strftime("%b %d, %Y"), value_style),
                Paragraph(due_value, value_style),
                Paragraph(f"<font color='{status_color}'>{payment.status.value}</font>", value_style)
            ]
        ]
        meta_table = Table(meta_data, colWidths=[1.75*inch, 1.75*inch, 1.75*inch, 1.75*inch])
        meta_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,0), 2),
            ('BOTTOMPADDING', (0,1), (-1,1), 25)
        ]))
        content.append(meta_table)
        
        # 3. Bill To & Bill From - 2 Column Table
        address_data = [
            [Paragraph("Billed To", section_header_style), Paragraph("Issued By", section_header_style)],
            [
                # Billed To Content
                [
                    Paragraph(org.name, value_style),
                    Paragraph(f"Organization ID: {org.id}", styles['Normal']),
                    Paragraph("Zambia", styles['Normal']),
                ],
                # Issued By Content
                [
                    Paragraph("Mifi-Pro", value_style),
                    Paragraph("Lusaka, Zambia", styles['Normal']),
                    Paragraph("support@mifi.pro", styles['Normal']),
                ]
            ]
        ]
        address_table = Table(address_data, colWidths=[3.5*inch, 3.5*inch])
        address_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,0), 4),
            ('BOTTOMPADDING', (0,1), (-1,1), 30)
        ]))
        content.append(address_table)
        
        # 4. Itemized Table
        content.append(Paragraph("Services & Subscription", section_header_style))
        content.append(Spacer(1, 4))
        table_data = [
            [Paragraph("DESCRIPTION", label_style), Paragraph("QTY", label_style), Paragraph("UNIT PRICE", label_style), Paragraph("AMOUNT", label_style)],
            [
                Paragraph(f"<b>{plan_display_name} Plan Subscription</b><br/><font size=8 color='grey'>30-day billing cycle</font>", styles['Normal']),
                "1",
                fmt_amount(payment.amount),
                fmt_amount(payment.amount)
            ]
        ]
        
        item_table = Table(table_data, colWidths=[3.8*inch, 0.6*inch, 1.3*inch, 1.3*inch])
        item_table.setStyle(TableStyle([
            ('LINEBELOW', (0,0), (-1,0), 0.5, colors.lightgrey),
            ('BOTTOMPADDING', (0,0), (-1,0), 6),
            ('TOPPADDING', (0,1), (-1,-1), 12),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
            ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ]))
        content.append(item_table)
        
        # 5. Totals - Detailed
        tax_amount = 0.0
        subtotal = payment.amount
        total = subtotal + tax_amount
        totals_data = [
            [Paragraph("Subtotal", label_style), Paragraph(fmt_amount(subtotal), value_style)],
            [Paragraph("Tax", label_style), Paragraph(fmt_amount(tax_amount), value_style)],
            [Paragraph("Total Amount Due", ParagraphStyle('TotalLabel', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold')), Paragraph(f"<b>{fmt_amount(total)}</b>", ParagraphStyle('TotalValue', parent=value_style, fontSize=12))]
        ]
        totals_table = Table(totals_data, colWidths=[5.1*inch, 1.9*inch])
        totals_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), subtle_grey),
            ('GRID', (0,0), (-1,-1), 0.25, colors.whitesmoke),
            ('ALIGN', (1,0), (1,-1), 'RIGHT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('PADDING', (0,0), (-1,-1), 6)
        ]))
        content.append(Spacer(1, 10))
        content.append(totals_table)
        content.append(Spacer(1, 40))
        
        # 6. Payment Instructions / Receipt
        if payment.status != PaymentStatus.PAID:
            content.append(Paragraph("Payment Instructions", section_header_style))
            content.append(Spacer(1, 6))
            
            if payment.gateway == "BANK_TRANSFER":
                instr_data = [
                    [Paragraph("Bank", label_style), Paragraph("Standard Chartered Bank (Zambia)", styles['Normal'])],
                    [Paragraph("Account Name", label_style), Paragraph("Mifi-Pro", styles['Normal'])],
                    [Paragraph("Account Number", label_style), Paragraph("01234567890", styles['Normal'])],
                    [Paragraph("Reference Code", label_style), Paragraph(f"<font color='red'><b>{payment.reference_code}</b></font>", styles['Normal'])],
                ]
                instr_table = Table(instr_data, colWidths=[1.5*inch, 5*inch])
                instr_table.setStyle(TableStyle([
                    ('GRID', (0,0), (-1,-1), 0.25, colors.whitesmoke),
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('BACKGROUND', (0,0), (0,-1), colors.whitesmoke),
                    ('PADDING', (0,0), (-1,-1), 6)
                ]))
                content.append(instr_table)
                content.append(Spacer(1, 10))
                content.append(Paragraph("<i>Please use the Reference Code exactly as shown above to ensure automatic activation.</i>", styles['Normal']))
            elif payment.gateway == "LIPILA":
                 content.append(Paragraph(f"Please complete the Mobile Money prompt sent to <b>{payment.phone_number}</b>.", styles['Normal']))
            else:
                 content.append(Paragraph(f"Please complete your payment via {payment.gateway.value}.", styles['Normal']))
        else:
             content.append(HRFlowable(width="100%", thickness=0.5, color=colors.whitesmoke, spaceAfter=10))
             content.append(Paragraph("RECEIPT OF PAYMENT", section_header_style))
             content.append(Paragraph(f"Transaction successfully processed via <b>{payment.gateway.value}</b> on {datetime.now().strftime('%b %d, %Y')}.", styles['Normal']))
             content.append(Paragraph("Thank you for choosing Mifi-Pro. Your subscription is active.", styles['Normal']))
             content.append(Spacer(1, 15))

        # 7. Footer
        content.append(Spacer(1, 60))
        content.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey, spaceAfter=8))
        content.append(Paragraph("Mifi-Pro - Leading Digital Lending Infrastructure in Zambia", label_style))
        content.append(Paragraph("Questions? Contact support@mifi.pro", label_style))

        doc.build(content)
        return file_path
