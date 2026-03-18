"""
PDF Generator for Prediction Results
Generates downloadable PDF reports for disease prediction results
"""
import os
import json
from datetime import datetime
from pathlib import Path

try:
    from reportlab.lib.pagesizes import letter, A4, landscape
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError as e:
    REPORTLAB_AVAILABLE = False
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"reportlab not available: {e}. PDF generation will be disabled.")


try:
    BASE_DIR = Path(__file__).resolve().parent.parent
    disease_info_path = BASE_DIR / "disease_info.json"
    if disease_info_path.exists():
        with open(disease_info_path, "r", encoding="utf-8") as f:
            DISEASE_INFO = json.load(f)
    else:
        DISEASE_INFO = {}
except Exception:
    DISEASE_INFO = {}


def generate_prediction_pdf(prediction, user, image_path, topk_results, all_models=None, ensemble_top=None):
    """
    Generate a PDF report for a prediction result
    
    Args:
        prediction: Prediction database object
        user: User database object
        image_path: Path to the uploaded image
        topk_results: List of top-k prediction results
        all_models: Optional list of all model results
        ensemble_top: Optional ensemble results
    
    Returns:
        Path to generated PDF file, or None if generation failed
    """
    if not REPORTLAB_AVAILABLE:
        return None
    
    try:
        pdfs_dir = Path('static') / 'pdfs'
        pdfs_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        pdf_filename = f'prediction_{prediction.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        pdf_path = pdfs_dir / pdf_filename
        
        doc = SimpleDocTemplate(str(pdf_path), pagesize=letter,
                               rightMargin=72, leftMargin=72,
                               topMargin=72, bottomMargin=18)
        
        elements = []
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a73e8'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#34a853'),
            spaceAfter=12,
            spaceBefore=12
        )
        
        logo_path = None
        try:
            candidates = [
                BASE_DIR / "images" / "logo.png",
                BASE_DIR / "static" / "img" / "logo.png"
            ]
            for p in candidates:
                if p.exists():
                    logo_path = p
                    break
        except Exception:
            logo_path = None
        
        if logo_path:
            try:
                logo_img = RLImage(str(logo_path))
                logo_img.hAlign = 'CENTER'
                max_width = 1.5 * inch
                if logo_img.drawWidth > 0:
                    ratio = max_width / float(logo_img.drawWidth)
                    logo_img.drawWidth = max_width
                    logo_img.drawHeight = logo_img.drawHeight * ratio
                elements.append(logo_img)
                elements.append(Spacer(1, 0.15*inch))
            except Exception:
                pass
        
        elements.append(Paragraph("Leafora AI Disease Detection Report", title_style))
        elements.append(Spacer(1, 0.2*inch))
        
        elements.append(Paragraph(f"<b>Report Date:</b> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
        elements.append(Paragraph(f"<b>User:</b> {user.username} ({user.email})", styles['Normal']))
        elements.append(Paragraph(f"<b>Prediction ID:</b> {prediction.id}", styles['Normal']))
        elements.append(Spacer(1, 0.3*inch))
        
        if image_path and os.path.exists(image_path):
            try:
                elements.append(Paragraph("Analyzed Image", heading_style))
                img = RLImage(image_path)
                img.hAlign = 'CENTER'
                max_width = 4.5 * inch
                if img.drawWidth > 0:
                    ratio = max_width / float(img.drawWidth)
                    img.drawWidth = max_width
                    img.drawHeight = img.drawHeight * ratio
                elements.append(img)
                elements.append(Spacer(1, 0.3*inch))
            except Exception:
                pass
        
        elements.append(Paragraph("Top Prediction", heading_style))
        top1 = topk_results[0] if topk_results else None
        if top1:
            elements.append(Paragraph(f"<b>Disease:</b> {top1.get('label', 'Unknown')}", styles['Normal']))
            confidence = top1.get('confidence', 0)
            elements.append(Paragraph(f"<b>Confidence:</b> {confidence:.2f}%", styles['Normal']))
            label = top1.get('label') or prediction.result
            rec_text = DISEASE_INFO.get(label) or DISEASE_INFO.get(prediction.result) or "No specific treatment information available. Please consult with an agricultural expert."
            elements.append(Paragraph(f"<b>Treatment Recommendation:</b> {rec_text}", styles['Normal']))
        elements.append(Spacer(1, 0.2*inch))
        
        if len(topk_results) > 1:
            elements.append(Paragraph("Top 5 Predictions", heading_style))
            prediction_data = [['Rank', 'Disease', 'Confidence']]
            for i, result in enumerate(topk_results[:5], 1):
                prediction_data.append([
                    f"#{i}",
                    result.get('label', 'Unknown'),
                    f"{result.get('confidence', 0):.2f}%"
                ])
            
            prediction_table = Table(prediction_data, colWidths=[0.8*inch, 3.5*inch, 1.5*inch])
            prediction_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a73e8')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
            ]))
            elements.append(prediction_table)
            elements.append(Spacer(1, 0.3*inch))
        
        if ensemble_top and len(ensemble_top) > 0:
            elements.append(Paragraph("Ensemble Results", heading_style))
            ensemble_data = [['Rank', 'Disease', 'Probability']]
            for i, result in enumerate(ensemble_top[:5], 1):
                prob = result.get('prob', 0) * 100 if 'prob' in result else result.get('confidence', 0)
                ensemble_data.append([
                    f"#{i}",
                    result.get('label', 'Unknown'),
                    f"{prob:.2f}%"
                ])
            
            ensemble_table = Table(ensemble_data, colWidths=[0.8*inch, 3.5*inch, 1.5*inch])
            ensemble_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34a853')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.lightgreen),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(ensemble_table)
            elements.append(Spacer(1, 0.3*inch))
        
        if all_models and len(all_models) > 0:
            elements.append(Paragraph("All Models Predictions", heading_style))
            for model_result in all_models:
                model_name = model_result.get('model_name', model_result.get('model', 'Unknown Model'))
                elements.append(Paragraph(f"<b>Model:</b> {model_name}", styles['Normal']))
                if model_result.get('topk') and len(model_result['topk']) > 0:
                    top_pred = model_result['topk'][0]
                    elements.append(Paragraph(
                        f"  Top Prediction: {top_pred.get('label', 'Unknown')} "
                        f"({top_pred.get('confidence', 0):.2f}%)",
                        styles['Normal']
                    ))
                elements.append(Spacer(1, 0.1*inch))
            elements.append(Spacer(1, 0.2*inch))
        
        if topk_results:
            elements.append(Paragraph("Disease Descriptions and Recommendations", heading_style))
            for i, result in enumerate(topk_results[:5], 1):
                label = result.get('label', 'Unknown')
                confidence = result.get('confidence', 0)
                info_text = DISEASE_INFO.get(label) or "No specific treatment information available. Please consult with an agricultural expert."
                elements.append(Paragraph(f"<b>{i}. {label}</b> ({confidence:.2f}% confidence)", styles['Normal']))
                elements.append(Paragraph(info_text, styles['Normal']))
                elements.append(Spacer(1, 0.1*inch))
            elements.append(Spacer(1, 0.3*inch))
        
        elements.append(Spacer(1, 0.3*inch))
        elements.append(Paragraph(
            "<i>This report was generated by Leafora AI - AI-Powered Plant Disease Detection System</i>",
            styles['Italic']
        ))
        elements.append(Paragraph(
            "<i>For critical decisions, please consult with an agricultural expert</i>",
            styles['Italic']
        ))
        
        # Build PDF
        try:
            doc.build(elements)
            return str(pdf_path)
        except Exception as build_error:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error building PDF document: {build_error}")
            logger.error(traceback.format_exc())
            return None
    except ImportError as import_error:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"ReportLab not available: {import_error}")
        return None
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating prediction PDF: {e}")
        logger.error(traceback.format_exc())
        return None


def generate_admin_table_pdf(title, columns, rows, subtitle=None):
    """
    Generate a themed PDF report for admin table exports.

    Args:
        title: Main report title
        columns: List of column names
        rows: List of row values (list/tuple per row)
        subtitle: Optional context/filter text

    Returns:
        bytes for PDF content, or None if generation fails
    """
    if not REPORTLAB_AVAILABLE:
        return None

    try:
        from io import BytesIO

        output = BytesIO()
        doc = SimpleDocTemplate(
            output,
            pagesize=landscape(A4),
            rightMargin=30,
            leftMargin=30,
            topMargin=28,
            bottomMargin=24
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'AdminTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor('#0C2235'),
            alignment=TA_LEFT,
            spaceAfter=10
        )
        meta_style = ParagraphStyle(
            'AdminMeta',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#425B6E'),
            spaceAfter=6
        )
        cell_style = ParagraphStyle(
            'AdminCell',
            parent=styles['Normal'],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#EAF6FF')
        )

        elements = []

        logo_path = None
        try:
            candidates = [
                BASE_DIR / "images" / "logo.png",
                BASE_DIR / "static" / "img" / "logo.png"
            ]
            for p in candidates:
                if p.exists():
                    logo_path = p
                    break
        except Exception:
            logo_path = None

        if logo_path:
            try:
                logo_img = RLImage(str(logo_path))
                logo_img.hAlign = 'LEFT'
                logo_img.drawWidth = 1.0 * inch
                logo_img.drawHeight = 1.0 * inch
                elements.append(logo_img)
            except Exception:
                pass

        elements.append(Paragraph(title, title_style))
        elements.append(Paragraph(
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Leafora AI Admin",
            meta_style
        ))
        if subtitle:
            elements.append(Paragraph(subtitle, meta_style))
        elements.append(Spacer(1, 8))

        safe_columns = [str(c) for c in columns]
        safe_rows = []
        for row in rows:
            safe_cells = []
            for cell in row:
                text = '' if cell is None else str(cell)
                text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                safe_cells.append(Paragraph(text, cell_style))
            safe_rows.append(safe_cells)

        table_data = [safe_columns] + safe_rows if safe_rows else [safe_columns]
        col_count = max(1, len(safe_columns))
        usable_width = landscape(A4)[0] - 60
        col_width = usable_width / col_count
        table = Table(table_data, colWidths=[col_width] * col_count, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0C2235')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#A5EFFE')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 7),
            ('TOPPADDING', (0, 0), (-1, 0), 7),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#0B1218'), colors.HexColor('#101A22')]),
            ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#29465D')),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 1), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ]))

        elements.append(table)
        doc.build(elements)
        return output.getvalue()
    except Exception:
        return None

