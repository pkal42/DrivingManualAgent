"""
Sample PDF Generator for Testing

This script creates sample driving manual PDFs for testing the indexer pipeline.
Uses reportlab to generate multi-page PDFs with text and placeholder images.

Requirements:
    pip install reportlab

Usage:
    python generate_test_pdfs.py --output-dir ../../../data/manuals
"""

import argparse
from datetime import datetime
from pathlib import Path

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
    )
except ImportError:
    print("Error: reportlab not installed. Install with: pip install reportlab")
    exit(1)


def create_california_manual(output_path: str):
    """
    Create a sample California DMV driving manual PDF.
    
    Args:
        output_path: Path where PDF will be saved
    """
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#003DA5'),
        spaceAfter=30,
    )
    
    story.append(Paragraph("California Driver Handbook", title_style))
    story.append(Spacer(1, 12))
    
    # Metadata
    story.append(Paragraph(f"<b>State:</b> California", styles['Normal']))
    story.append(Paragraph(f"<b>Edition:</b> 2024", styles['Normal']))
    story.append(Paragraph(f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d')}", styles['Normal']))
    story.append(Spacer(1, 24))
    
    # Chapter 1: Traffic Laws
    story.append(Paragraph("Chapter 1: Traffic Laws and Road Signs", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    traffic_text = """
    California has specific traffic laws that all drivers must follow. 
    Speed limits vary by location: 25 mph in residential areas, 65 mph on most highways, 
    and 70 mph on some rural interstate highways. Drivers must stop at red lights and 
    stop signs, yield to pedestrians in crosswalks, and maintain a safe following distance.
    
    Right-of-way rules are critical for safe driving. At four-way stops, the first vehicle 
    to arrive has the right of way. When two vehicles arrive simultaneously, the vehicle 
    on the right has priority. Emergency vehicles with active sirens and lights always 
    have the right of way.
    """
    story.append(Paragraph(traffic_text, styles['Normal']))
    story.append(Spacer(1, 12))
    
    # Road signs section
    story.append(Paragraph("Common Road Signs", styles['Heading3']))
    story.append(Spacer(1, 12))
    
    signs_data = [
        ['Sign Type', 'Shape', 'Color', 'Meaning'],
        ['Stop', 'Octagon', 'Red', 'Complete stop required'],
        ['Yield', 'Triangle', 'Red/White', 'Give right of way'],
        ['Speed Limit', 'Rectangle', 'White/Black', 'Maximum speed allowed'],
        ['Warning', 'Diamond', 'Yellow/Black', 'Hazard ahead'],
    ]
    
    table = Table(signs_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 2.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(table)
    story.append(PageBreak())
    
    # Chapter 2: Safe Driving
    story.append(Paragraph("Chapter 2: Safe Driving Practices", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    safe_driving_text = """
    Defensive driving is essential for preventing accidents. Always scan the road ahead 
    and check mirrors regularly. Maintain a following distance of at least three seconds 
    in good weather and increase it in rain or fog. Avoid distractions such as mobile 
    phones, eating, or adjusting the radio while driving.
    
    When changing lanes, use turn signals at least 100 feet before the maneuver. Check 
    blind spots by turning your head, as mirrors don't show everything. Never change 
    lanes in an intersection or while crossing railroad tracks.
    
    In adverse weather conditions, reduce speed and increase following distance. 
    Turn on headlights when visibility is reduced. If hydroplaning occurs, ease off 
    the accelerator and steer straight until traction is regained.
    """
    story.append(Paragraph(safe_driving_text, styles['Normal']))
    story.append(PageBreak())
    
    # Chapter 3: Parking
    story.append(Paragraph("Chapter 3: Parking Regulations", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    parking_text = """
    Parking regulations in California are strictly enforced. Never park within 15 feet 
    of a fire hydrant, in front of a driveway, or within a crosswalk. When parking on 
    a hill, turn wheels toward the curb when facing downhill and away from the curb 
    when facing uphill. Set the parking brake before exiting the vehicle.
    
    Red curbs indicate no stopping, standing, or parking. Blue curbs are reserved for 
    disabled persons with proper placards. White curbs allow passenger loading only, 
    and green curbs permit parking for limited times (usually 10-30 minutes).
    
    Handicapped parking spaces require a valid disabled person placard or license plate. 
    Unauthorized use can result in fines up to $1,000 and vehicle impoundment.
    """
    story.append(Paragraph(parking_text, styles['Normal']))
    story.append(PageBreak())
    
    # Build PDF
    doc.build(story)
    print(f"Created: {output_path}")


def create_texas_manual(output_path: str):
    """
    Create a sample Texas DPS driving manual PDF.
    
    Args:
        output_path: Path where PDF will be saved
    """
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#BF0A30'),
        spaceAfter=30,
    )
    
    story.append(Paragraph("Texas Driver Handbook", title_style))
    story.append(Spacer(1, 12))
    
    # Metadata
    story.append(Paragraph(f"<b>State:</b> Texas", styles['Normal']))
    story.append(Paragraph(f"<b>Edition:</b> 2024", styles['Normal']))
    story.append(Paragraph(f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d')}", styles['Normal']))
    story.append(Spacer(1, 24))
    
    # Chapter 1: Texas Traffic Laws
    story.append(Paragraph("Chapter 1: Texas Traffic Laws", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    traffic_text = """
    Texas traffic laws are designed to ensure the safety of all road users. The maximum 
    speed limit on Texas highways can reach up to 85 mph on certain toll roads, while 
    urban areas typically have limits of 30-45 mph. School zones require reduced speeds 
    of 20 mph when children are present.
    
    Texas is a "no tolerance" state for drinking and driving. Drivers under 21 with any 
    detectable alcohol in their system face immediate license suspension. For drivers 
    21 and over, the legal limit is 0.08% blood alcohol content (BAC).
    
    Cell phone use while driving is restricted for certain drivers. Drivers under 18 
    and drivers in school zones cannot use handheld devices. Texting while driving is 
    prohibited for all drivers statewide.
    """
    story.append(Paragraph(traffic_text, styles['Normal']))
    story.append(PageBreak())
    
    # Chapter 2: Right of Way
    story.append(Paragraph("Chapter 2: Right of Way Rules", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    right_of_way_text = """
    Understanding right-of-way rules prevents accidents at intersections. When approaching 
    an intersection without signals, the vehicle on the right has the right of way if both 
    vehicles arrive simultaneously. At T-intersections, through traffic has priority over 
    turning traffic.
    
    Pedestrians always have the right of way in marked crosswalks. Drivers must yield and 
    may not pass vehicles stopped at crosswalks. At unmarked intersections, drivers must 
    yield to pedestrians crossing the roadway.
    
    Emergency vehicles with active lights and sirens require all traffic to pull to the 
    right and stop. Funeral processions have the right of way when led by a funeral escort 
    vehicle. Drivers should not interrupt or pass through funeral processions.
    """
    story.append(Paragraph(right_of_way_text, styles['Normal']))
    story.append(PageBreak())
    
    # Chapter 3: Highway Safety
    story.append(Paragraph("Chapter 3: Highway Driving Safety", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    highway_text = """
    Highway driving requires heightened awareness and specific techniques. When merging 
    onto highways, use acceleration lanes to match highway speed before merging. Check 
    mirrors and blind spots, signal early, and merge smoothly into traffic gaps.
    
    Lane discipline is important on multi-lane highways. The left lane is for passing; 
    slower traffic should keep right. Avoid sudden lane changes and never cross multiple 
    lanes at once. Maintain consistent speed to improve traffic flow.
    
    If your vehicle breaks down on the highway, safely pull to the shoulder as far right 
    as possible. Turn on hazard lights, exit from the passenger side if safe, and stay 
    away from the vehicle. Call for assistance and wait in a safe location.
    """
    story.append(Paragraph(highway_text, styles['Normal']))
    
    # Build PDF
    doc.build(story)
    print(f"Created: {output_path}")


def main():
    """Generate sample PDF driving manuals."""
    parser = argparse.ArgumentParser(
        description='Generate sample PDF driving manuals for testing'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='../../../data/manuals',
        help='Output directory for generated PDFs'
    )
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate PDFs
    print("Generating sample driving manual PDFs...")
    print("-" * 60)
    
    california_path = output_dir / 'california-dmv-handbook-2024.pdf'
    create_california_manual(str(california_path))
    
    texas_path = output_dir / 'texas-driver-handbook-2024.pdf'
    create_texas_manual(str(texas_path))
    
    print("-" * 60)
    print(f"Generated 2 sample PDFs in: {output_dir}")
    print("\nYou can now upload these PDFs to Azure Blob Storage:")
    print(f"  az storage blob upload-batch \\")
    print(f"    -d pdfs \\")
    print(f"    -s {output_dir} \\")
    print(f"    --account-name YOUR-STORAGE-ACCOUNT-NAME \\")
    print(f"    --auth-mode login")
    print("\nReplace YOUR-STORAGE-ACCOUNT-NAME with your actual storage account name")


if __name__ == '__main__':
    main()
