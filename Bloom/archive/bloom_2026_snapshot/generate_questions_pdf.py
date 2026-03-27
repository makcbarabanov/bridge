#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для генерации PDF файла с 20 вопросами из вопросника BLOOM
"""

questions = [
    "Что для тебя по-настоящему важно в жизни прямо сейчас?",
    "Если бы у тебя было неограниченное время и ресурсы, чем бы ты занимался?",
    "Чего ты боишься больше всего?",
    "Что бы ты сделал, если бы точно знал, что не провалишься?",
    "Каким человеком ты хочешь быть через год?",
    "Что ты хочешь, чтобы о тебе говорили люди?",
    "Какую проблему в мире ты хотел бы решить?",
    "Что делает тебя по-настоящему счастливым?",
    "Если бы тебе осталось жить год, как бы ты его прожил?",
    "Что ты откладываешь уже долгое время?",
    "Какой след ты хочешь оставить в этом мире?",
    "Что бы ты посоветовал себе 10 лет назад?",
    "Что тебя вдохновляет и заряжает энергией?",
    "От чего ты готов отказаться ради своей цели?",
    "Как ты поймёшь, что достиг успеха?",
    "Что мешает тебе начать прямо сейчас?",
    "Какие у тебя есть сильные стороны?",
    "Кто те люди, которых ты хочешь сделать счастливее?",
    "Что ты будешь чувствовать, когда достигнешь своей цели?",
    "Какой первый шаг ты можешь сделать уже сегодня?"
]

def generate_pdf_fpdf():
    """Генерация PDF с использованием fpdf"""
    try:
        from fpdf import FPDF
        
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        # Настройка шрифта для поддержки кириллицы
        try:
            pdf.add_font('DejaVu', '', 'DejaVuSansCondensed.ttf', uni=True)
            pdf.set_font('DejaVu', '', 14)
        except:
            # Fallback на стандартный шрифт
            pdf.set_font('Arial', '', 12)
        
        # Заголовок
        pdf.set_font_size(18)
        pdf.cell(0, 10, '🌸 BLOOM Questionnaire', 0, 1, 'C')
        pdf.ln(5)
        pdf.set_font_size(12)
        pdf.cell(0, 8, '20 глубоких вопросов о жизни, целях и мечтах', 0, 1, 'C')
        pdf.ln(10)
        
        # Вопросы
        pdf.set_font_size(11)
        for i, question in enumerate(questions, 1):
            pdf.set_font('DejaVu', 'B', 11) if 'DejaVu' in str(pdf.get_font()) else pdf.set_font('Arial', 'B', 11)
            pdf.cell(0, 8, f'Вопрос {i}:', 0, 1, 'L')
            pdf.set_font('DejaVu', '', 11) if 'DejaVu' in str(pdf.get_font()) else pdf.set_font('Arial', '', 11)
            pdf.multi_cell(0, 6, question, 0, 'L')
            pdf.ln(5)
        
        output_file = 'bloom_questions.pdf'
        pdf.output(output_file)
        print(f"✅ PDF успешно создан: {output_file}")
        return True
    except ImportError:
        print("❌ Библиотека fpdf не установлена")
        return False
    except Exception as e:
        print(f"❌ Ошибка при создании PDF (fpdf): {e}")
        return False

def generate_pdf_reportlab():
    """Генерация PDF с использованием reportlab"""
    try:
        import os
        import platform
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
        
        output_file = 'bloom_questions.pdf'
        doc = SimpleDocTemplate(output_file, pagesize=A4)
        story = []
        
        # Регистрация шрифта с поддержкой кириллицы
        # Пробуем найти системный шрифт Windows с поддержкой кириллицы
        font_registered = False
        normal_font_name = 'Arial'
        bold_font_name = 'ArialBold'
        
        if platform.system() == 'Windows':
            # Пути к стандартным шрифтам Windows
            arial_path = 'C:/Windows/Fonts/arial.ttf'
            arial_bold_path = 'C:/Windows/Fonts/arialbd.ttf'
            times_path = 'C:/Windows/Fonts/times.ttf'
            times_bold_path = 'C:/Windows/Fonts/timesbd.ttf'
            
            # Пробуем Arial
            if os.path.exists(arial_path):
                try:
                    pdfmetrics.registerFont(TTFont('Arial', arial_path))
                    if os.path.exists(arial_bold_path):
                        pdfmetrics.registerFont(TTFont('ArialBold', arial_bold_path))
                    normal_font_name = 'Arial'
                    bold_font_name = 'ArialBold'
                    font_registered = True
                    print("✅ Загружен шрифт Arial с поддержкой кириллицы")
                except Exception as e:
                    print(f"⚠️ Не удалось загрузить Arial: {e}")
            
            # Если Arial не сработал, пробуем Times New Roman
            if not font_registered and os.path.exists(times_path):
                try:
                    pdfmetrics.registerFont(TTFont('Times', times_path))
                    if os.path.exists(times_bold_path):
                        pdfmetrics.registerFont(TTFont('TimesBold', times_bold_path))
                    normal_font_name = 'Times'
                    bold_font_name = 'TimesBold'
                    font_registered = True
                    print("✅ Загружен шрифт Times New Roman с поддержкой кириллицы")
                except Exception as e:
                    print(f"⚠️ Не удалось загрузить Times: {e}")
        
        if not font_registered:
            # Fallback: используем встроенные шрифты (могут не поддерживать кириллицу)
            normal_font_name = 'Helvetica'
            bold_font_name = 'Helvetica-Bold'
            print("⚠️ Использую стандартный шрифт (может быть проблема с кириллицей)")
        
        # Настройка стилей с правильным шрифтом
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            fontName=bold_font_name,
            textColor=colors.HexColor('#333333'),
            spaceAfter=10,
            alignment=TA_CENTER
        )
        
        intro_style = ParagraphStyle(
            'CustomIntro',
            parent=styles['Normal'],
            fontSize=11,
            fontName=normal_font_name,
            textColor=colors.HexColor('#555555'),
            spaceAfter=15,
            alignment=TA_CENTER,
            leading=14
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Normal'],
            fontSize=12,
            fontName=bold_font_name,
            textColor=colors.HexColor('#666666'),
            spaceAfter=20,
            alignment=TA_CENTER
        )
        
        question_header_style = ParagraphStyle(
            'QuestionHeader',
            parent=styles['Normal'],
            fontSize=11,
            fontName=bold_font_name,
            spaceAfter=6,
            leftIndent=0,
            textColor=colors.HexColor('#4CAF50')
        )
        
        question_style = ParagraphStyle(
            'Question',
            parent=styles['Normal'],
            fontSize=12,
            fontName=normal_font_name,
            spaceAfter=15,
            leftIndent=0,
            leading=16,
            alignment=TA_LEFT
        )
        
        # Заголовок
        story.append(Paragraph('🌸 BLOOM Questionnaire', title_style))
        story.append(Spacer(1, 0.3*cm))
        
        # Описание
        intro_text = ('20 вопросов из опросника AI ассистента Bloom '
                     'для раскрытия своих желаний')
        story.append(Paragraph(intro_text, intro_style))
        story.append(Spacer(1, 0.5*cm))
        
        # Вопросы
        for i, question in enumerate(questions, 1):
            # Используем жирный стиль напрямую для заголовка вопроса
            story.append(Paragraph(f'Вопрос {i}:', question_header_style))
            story.append(Paragraph(question, question_style))
            story.append(Spacer(1, 0.2*cm))
        
        doc.build(story)
        print(f"✅ PDF успешно создан: {output_file}")
        print(f"✅ Использован шрифт: {normal_font_name} (поддержка кириллицы: {font_registered})")
        return True
    except ImportError:
        print("❌ Библиотека reportlab не установлена")
        return False
    except Exception as e:
        print(f"❌ Ошибка при создании PDF (reportlab): {e}")
        import traceback
        traceback.print_exc()
        return False

def generate_html_for_pdf():
    """Создание HTML файла, который можно конвертировать в PDF"""
    html_content = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BLOOM Questionnaire - 20 вопросов</title>
    <style>
        @page {
            margin: 2cm;
            size: A4;
        }
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #e0e0e0;
        }
        h1 {
            color: #333;
            margin: 0 0 10px 0;
            font-size: 28px;
        }
        .subtitle {
            color: #666;
            font-size: 16px;
            margin-top: 10px;
        }
        .question {
            margin-bottom: 25px;
            padding: 15px;
            background-color: #f9f9f9;
            border-left: 4px solid #4CAF50;
            page-break-inside: avoid;
        }
        .question-number {
            font-weight: bold;
            color: #4CAF50;
            font-size: 12px;
            margin-bottom: 8px;
            text-transform: uppercase;
        }
        .question-text {
            font-size: 14px;
            line-height: 1.7;
            color: #333;
        }
        .footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            text-align: center;
            color: #999;
            font-size: 12px;
        }
        @media print {
            body {
                padding: 0;
            }
            .question {
                page-break-inside: avoid;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🌸 BLOOM Questionnaire</h1>
        <p class="subtitle">20 глубоких вопросов о жизни, целях и мечтах</p>
    </div>
"""
    
    for i, question in enumerate(questions, 1):
        html_content += f"""
    <div class="question">
        <div class="question-number">Вопрос {i} из {len(questions)}</div>
        <div class="question-text">{question}</div>
    </div>
"""
    
    html_content += """
    <div class="footer">
        <p>🌸 BLOOM - Помогаю тебе найти свой путь через осознанные вопросы</p>
    </div>
</body>
</html>
"""
    
    html_file = 'bloom_questions.html'
    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ HTML файл создан: {html_file}")
    print("💡 Откройте файл в браузере и используйте 'Печать' → 'Сохранить как PDF' для создания PDF")
    return html_file

if __name__ == "__main__":
    print("🔍 Попытка создать PDF файл...")
    
    # Пробуем reportlab
    if generate_pdf_reportlab():
        exit(0)
    
    # Пробуем fpdf
    if generate_pdf_fpdf():
        exit(0)
    
    # Если библиотеки не найдены, создаём HTML
    print("\n⚠️  PDF библиотеки не найдены. Создаю HTML файл для конвертации...")
    generate_html_for_pdf()

