from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, Dict
import uvicorn
from io import BytesIO
from PIL import Image
import cairosvg
import base64
import re
import xml.etree.ElementTree as ET
from google import genai
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Business Analyzer API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gemini client - unchanged
GEMINI_API_KEY = "enter your gemini api key"
client = genai.Client(api_key=GEMINI_API_KEY)

# PROMPT - unchanged
PROMPT = """
### 1. Analysis Phase
- **Transcribe:** Recreate the original question text, diagram and image exactly as it appears (font, layout, bolding, content, curve) on the LEFT side of the canvas.
- **Identify & Highlight:**
  1. **The Goal:** Locate the specific question asked (e.g., "What is the Gross Profit Margin?"). **Draw a light red box** around this text in the recreation.
  2. **Key Data Points:** Locate the specific numbers required for the calculation (e.g., "SAR 35", "SAR 5", "SAR 100"). **Draw thin colored boxes** (matching the logic below) directly around these data points within the text/table.
- **Constraints:** Final answers should match the multiple-choice options provided.

### 2. Design & Layout Rules (Strict)
- **Canvas:** Width >= 1200px. Divide into two zones:
  - **Left Zone (0-800px):** For the recreated question text and table.
  - **Right Zone (800px+):** For explanation cards/boxes.
- **Color Coding:**
  - **Pink/Red:** The Goal / Core Equation.
  - **Blue:** Condition A (e.g., Input Costs/COGS).
  - **Green:** Condition B (e.g., Selling Price/Gross Profit calculation).
  - **Orange:** Final Calculation/Result.

### 3. Arrow Routing Logic (PRECISION FOCUS)
You must ensure arrows originate **directly from the bounding boxes** of the data they refer to and point to the corresponding step in the explanation zone.There MUST be no misalignment.
- **Tight Connection:** The start point of the arrow must touch the edge of the highlight box created in Step 1.
- **No Overlap:** Use "Manhattan geometry" (orthogonal lines) with specific channels:
  - **Top Channel:** For the Goal. Polyline going UP from the text, across the top, and dropping into the top-right box.
  - **Middle/Lower Channels:** For data points. Use the space between the text block and the sidebar to route lines horizontally.
- **Avoid:** Do not cross the text or other arrows.

### 4. Mathematical Formatting
- In the explanation boxes, render formulas to look like **LaTeX**:
  - Use `font-family="Times New Roman"` and `font-style="italic"` for variables.
  - Use `dy` attributes for superscripts/subscripts.
  - Clearly show the step-by-step substitution of values into the formula.

### 5. Output Requirements
- Return only one valid SVG code block.
- Ensure the SVG is responsive and all text is legible.
- The correct multiple-choice option should be visually emphasized (e.g., a circle or bold green text).

an ideal example looks like this:

<svg width="1400" height="750" viewBox="0 0 1400 750" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <!-- Arrow Markers -->
    <marker id="arrow-blue" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
      <path d="M0,0 L8,4 L0,8" fill="#0277bd" />
    </marker>
    <marker id="arrow-green" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
      <path d="M0,0 L8,4 L0,8" fill="#2e7d32" />
    </marker>
    <marker id="arrow-red" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
      <path d="M0,0 L8,4 L0,8" fill="#c62828" />
    </marker>
    <!-- Shadow Filter for Cards -->
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="2"/>
      <feOffset dx="2" dy="2" result="offsetblur"/>
      <feComponentTransfer>
        <feFuncA type="linear" slope="0.2"/>
      </feComponentTransfer>
      <feMerge>
        <feMergeNode/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>

  <!-- Background -->
  <rect width="100%" height="100%" fill="#ffffff" />

  <!-- ========================================= -->
  <!-- ZONE 1: BANK RECONCILIATION FORM (Left) -->
  <!-- ========================================= -->

  <g transform="translate(30, 40)">
    <!-- Header -->
    <text x="220" y="25" font-family="Arial, sans-serif" font-size="18" font-weight="bold" fill="#333" text-anchor="middle">Bank Reconciliation</text>
    <line x1="0" y1="35" x2="460" y2="35" stroke="#ccc" stroke-width="1"/>

    <!-- LEFT COLUMN (Bank Side) -->
    <g transform="translate(0, 50)" font-family="Arial, sans-serif" font-size="13">
      <text x="0" y="20">Bank statement</text>
      <text x="0" y="38">balance</text>
      <rect x="130" y="10" width="80" height="28" fill="#e3f2fd" stroke="#90caf9" stroke-width="1"/>
      <text x="170" y="29" text-anchor="middle" font-weight="bold" fill="#0277bd">6365.61</text>

      <text x="0" y="80" font-weight="bold">Add:</text>
      <text x="20" y="100">Deposits not</text>
      <text x="20" y="118">recorded</text>
      <rect x="130" y="90" width="80" height="28" fill="#e3f2fd" stroke="#90caf9" stroke-width="1"/>
      <text x="170" y="109" text-anchor="middle" font-weight="bold" fill="#0277bd">+ 750.75</text>

      <line x1="130" y1="125" x2="210" y2="125" stroke="#333"/>
      <!-- Anchor: Bank Subtotal -->
      <text x="170" y="145" text-anchor="middle" font-weight="bold">7116.36</text>
      <circle cx="215" cy="140" r="2" fill="#c62828"/>

      <text x="0" y="180" font-weight="bold">Less:</text>
      <text x="20" y="200">Outstanding</text>
      <text x="20" y="218">checks</text>

      <!-- Target: Outstanding Input -->
      <rect x="130" y="190" width="80" height="28" fill="#fff" stroke="#c62828" stroke-width="1.5"/>
      <text x="120" y="210" font-weight="bold">-</text>
      <line x1="130" y1="225" x2="210" y2="225" stroke="#333"/>
      <text x="170" y="210" text-anchor="middle" fill="#c62828" font-weight="bold" font-size="13">487.34</text>
    </g>

    <!-- RIGHT COLUMN (Book Side) -->
    <g transform="translate(230, 50)" font-family="Arial, sans-serif" font-size="13">
      <text x="0" y="20">Checkbook balance</text>
      <rect x="130" y="10" width="80" height="28" fill="#e3f2fd" stroke="#90caf9" stroke-width="1"/>
      <text x="170" y="29" text-anchor="middle" font-weight="bold" fill="#0277bd">6700.59</text>

      <text x="0" y="80" font-weight="bold">Add:</text>
      <text x="20" y="105">Interest Credit (IC)</text>
      <rect x="130" y="90" width="80" height="28" fill="#e3f2fd" stroke="#90caf9" stroke-width="1"/>
      <text x="170" y="109" text-anchor="middle" font-weight="bold" fill="#0277bd">+ 24.41</text>

      <line x1="130" y1="125" x2="210" y2="125" stroke="#333"/>
      <!-- Anchor: Book Subtotal -->
      <text x="170" y="145" text-anchor="middle" font-weight="bold">6,725.00</text>
      <circle cx="215" cy="140" r="2" fill="#2e7d32"/>

      <text x="0" y="180" font-weight="bold">Less:</text>
      <text x="20" y="205">Bank charges</text>

      <!-- Target: Charges Input -->
      <rect x="130" y="190" width="80" height="28" fill="#fff" stroke="#0277bd" stroke-width="1.5"/>
      <text x="120" y="210" font-weight="bold">-</text>
      <line x1="130" y1="225" x2="210" y2="225" stroke="#333"/>
      <text x="170" y="210" text-anchor="middle" fill="#0277bd" font-weight="bold" font-size="13">95.98</text>
    </g>

    <line x1="460" y1="0" x2="460" y2="300" stroke="#e0e0e0" stroke-width="2"/>
  </g>

  <!-- ========================================= -->
  <!-- ZONE 2: BANK STATEMENT (Center) -->
  <!-- ========================================= -->

  <g transform="translate(500, 40)">
    <text x="180" y="25" font-family="Arial, sans-serif" font-size="18" font-weight="bold" fill="#333" text-anchor="middle">Bank Statement</text>
    <line x1="0" y1="45" x2="380" y2="45" stroke="#999" stroke-dasharray="3,3"/>

    <!-- Table Header -->
    <g font-family="Courier New, monospace" font-size="11" font-weight="bold" fill="#555">
      <text x="0" y="65">CHECK</text>
      <text x="0" y="80">NUMBER</text>

      <text x="60" y="65">CHECKS AND</text>
      <text x="60" y="80">DEBITS</text>

      <text x="200" y="80">DEPOSITS</text>
      <text x="270" y="80">DATE</text>
      <text x="320" y="80">BALANCE</text>
    </g>
    <line x1="0" y1="90" x2="380" y2="90" stroke="#999" stroke-dasharray="3,3"/>

    <!-- Table Rows -->
    <g font-family="Courier New, monospace" font-size="12" fill="#333">
      <text x="200" y="110">911.28</text> <text x="270" y="110">3/5</text> <text x="320" y="110">7021.39</text>
      <text x="270" y="130">3/7</text> <text x="320" y="130">7932.67</text>
      <text x="0" y="150">662</text> <text x="60" y="150">448.16</text> <text x="270" y="150">3/11</text> <text x="320" y="150">7484.51</text>

      <!-- Highlight RC -->
      <rect x="120" y="160" width="70" height="16" fill="rgba(2,119,189,0.15)" stroke="none" rx="2"/>
      <text x="0" y="172">666</text> <text x="60" y="172">370.55</text>
      <text x="125" y="172" font-weight="bold" fill="#01579b">81.18 RC</text>
      <text x="200" y="172">420.16</text> <text x="270" y="172">3/16</text> <text x="320" y="172">7452.94</text>

      <text x="0" y="194">665</text> <text x="60" y="194">73.34</text>
      <text x="200" y="194">24.41 IC</text> <text x="270" y="194">3/20</text> <text x="320" y="194">7404.01</text>
      <text x="0" y="216">667</text> <text x="60" y="216">618.65</text> <text x="200" y="216">166.55</text> <text x="270" y="216">3/22</text> <text x="320" y="216">6618.81</text>

      <!-- Highlight SC -->
      <rect x="120" y="226" width="70" height="16" fill="rgba(2,119,189,0.15)" stroke="none" rx="2"/>
      <text x="0" y="238">669</text> <text x="60" y="238">238.40</text>
      <text x="125" y="238" font-weight="bold" fill="#01579b">14.80 SC</text>
      <text x="270" y="238">3/26</text> <text x="320" y="238">6365.61</text>
    </g>

    <line x1="0" y1="250" x2="380" y2="250" stroke="#999" stroke-dasharray="3,3"/>
    <foreignObject x="0" y="260" width="380" height="50">
      <div xmlns="http://www.w3.org/1999/xhtml" style="font-family:sans-serif; font-size:10px; color:#777; line-height:1.4;">
        Note that RC means Returned Check, SC means Service Charge, CP means Check Printing Charge, IC means Interest Credit, ATM means Automated Teller Machine.
      </div>
    </foreignObject>
  </g>

  <!-- ========================================= -->
  <!-- ZONE 3: EXPLANATION CARDS (Right) -->
  <!-- ========================================= -->

  <!-- Step 1 (Blue) -->
  <g transform="translate(1020, 40)">
    <rect x="0" y="0" width="340" height="150" rx="8" fill="#ffffff" stroke="#0277bd" stroke-width="2" filter="url(#shadow)"/>
    <rect x="0" y="0" width="340" height="40" rx="8" fill="#e1f5fe" stroke="none"/>
    <path d="M0,40 L340,40" stroke="#b3e5fc" stroke-width="1"/>

    <text x="20" y="26" font-family="Arial" font-size="16" font-weight="bold" fill="#0277bd">Step 1: Identify Charges</text>
    <text x="20" y="65" font-family="Arial" font-size="14" fill="#333">Scan statement for debits not in book:</text>
    <g font-family="monospace" font-size="13" fill="#333">
      <text x="30" y="90">• 81.18 (RC - Returned Check)</text>
      <text x="30" y="110">• 14.80 (SC - Service Charge)</text>
    </g>
    <text x="20" y="135" font-family="Arial" font-size="15" font-weight="bold" fill="#0277bd">Total Bank Charges = $95.98</text>
  </g>

  <!-- Step 2 (Green) -->
  <g transform="translate(1020, 230)">
    <rect x="0" y="0" width="340" height="150" rx="8" fill="#ffffff" stroke="#2e7d32" stroke-width="2" filter="url(#shadow)"/>
    <rect x="0" y="0" width="340" height="40" rx="8" fill="#e8f5e9" stroke="none"/>
    <path d="M0,40 L340,40" stroke="#c8e6c9" stroke-width="1"/>

    <text x="20" y="26" font-family="Arial" font-size="16" font-weight="bold" fill="#2e7d32">Step 2: Adjusted Balance</text>
    <text x="20" y="65" font-family="Arial" font-size="14" fill="#333">Calculate true checkbook balance:</text>
    <text x="30" y="90" font-family="Times New Roman" font-size="16" fill="#333">6,725.00 (Subtotal)</text>
    <text x="30" y="110" font-family="Times New Roman" font-size="16" fill="#d32f2f">- 95.98 (Charges)</text>
    <line x1="30" y1="115" x2="200" y2="115" stroke="#333"/>
    <text x="20" y="135" font-family="Arial" font-size="15" font-weight="bold" fill="#2e7d32">Adjusted Balance = $6,629.02</text>
  </g>

  <!-- Step 3 (Red) -->
  <g transform="translate(1020, 420)">
    <rect x="0" y="0" width="340" height="150" rx="8" fill="#ffffff" stroke="#c62828" stroke-width="2" filter="url(#shadow)"/>
    <rect x="0" y="0" width="340" height="40" rx="8" fill="#ffebee" stroke="none"/>
    <path d="M0,40 L340,40" stroke="#ffcdd2" stroke-width="1"/>

    <text x="20" y="26" font-family="Arial" font-size="16" font-weight="bold" fill="#c62828">Step 3: Solve Outstanding</text>
    <text x="20" y="65" font-family="Arial" font-size="14" fill="#333">Bank Subtotal - X = Adj. Balance</text>
    <text x="30" y="90" font-family="Times New Roman" font-size="16" fill="#333">7,116.36 - X = 6,629.02</text>
    <text x="30" y="110" font-family="Times New Roman" font-size="16" fill="#333">X = 7,116.36 - 6,629.02</text>
    <text x="20" y="135" font-family="Arial" font-size="15" font-weight="bold" fill="#c62828">Outstanding Checks = $487.34</text>
  </g>

  <!-- ========================================= -->
  <!-- ARROWS (Strict Routing, Bottom-Center Targets) -->
  <!-- ========================================= -->

  <!-- Arrow 1 (Blue Solid): Highlights -> Step 1 Box -->
  <path d="M 695 212 L 940 212 L 940 115 L 1010 115" fill="none" stroke="#0277bd" stroke-width="2" marker-end="url(#arrow-blue)"/>
  <!-- Connecting bottom highlight to the main path -->
  <path d="M 695 278 L 940 278 L 940 212" fill="none" stroke="#0277bd" stroke-width="2"/>
  <circle cx="695" cy="212" r="3" fill="#0277bd"/>
  <circle cx="695" cy="278" r="3" fill="#0277bd"/>

  <!-- Arrow 2 (Blue Dashed): Step 1 Box -> Charges Input (Bottom Center) -->
  <!-- Target Box Center X = 430, Bottom Y = 308 -->
  <path d="M 1020 175 L 920 175 L 920 340 L 430 340 L 430 316" fill="none" stroke="#0277bd" stroke-width="2" stroke-dasharray="6,4" marker-end="url(#arrow-blue)"/>

  <!-- Arrow 3 (Green Solid): Book Subtotal -> Step 2 Box -->
  <path d="M 470 230 L 495 230 L 495 360 L 960 360 L 960 305 L 1010 305" fill="none" stroke="#2e7d32" stroke-width="2" marker-end="url(#arrow-green)"/>

  <!-- Arrow 4 (Red Solid): Bank Subtotal -> Step 3 Box -->
  <path d="M 245 230 L 255 230 L 255 420 L 980 420 L 980 495 L 1010 495" fill="none" stroke="#c62828" stroke-width="2" marker-end="url(#arrow-red)"/>

  <!-- Arrow 5 (Red Dashed): Step 3 Result -> Outstanding Input (Bottom Center) -->
  <!-- Target Box Center X = 200, Bottom Y = 308 -->
  <path d="M 1020 540 L 200 540 L 200 316" fill="none" stroke="#c62828" stroke-width="2" stroke-dasharray="6,4" marker-end="url(#arrow-red)"/>

</svg>

Each step card has one color, the numbers used in that colored card should matches the arrow line color and number box color.

You are a AI Agent. You must strictly follow all the above instructions.


"""

def validate_and_clean_svg(svg_content: str) -> str:
    """
    Clean and validate SVG to ensure it's mobile-compatible and well-formed
    """
    try:
        # Remove any markdown or code block wrappers
        clean_svg = svg_content.strip()
        
        # Remove markdown code blocks
        clean_svg = re.sub(r'^```(svg|xml)?\s*', '', clean_svg)
        clean_svg = re.sub(r'\s*```$', '', clean_svg)
        clean_svg = clean_svg.strip()
        
        # Ensure it starts with <svg
        if not clean_svg.startswith('<svg'):
            svg_start = clean_svg.find('<svg')
            if svg_start != -1:
                clean_svg = clean_svg[svg_start:]
            else:
                clean_svg = f'<svg width="100%" height="auto" viewBox="0 0 1200 800" xmlns="http://www.w3.org/2000/svg">{clean_svg}</svg>'
        
        # Parse and optimize SVG for mobile
        try:
            root = ET.fromstring(clean_svg)
            
            root.set('width', '100%')
            root.set('height', 'auto')
            root.set('preserveAspectRatio', 'xMidYMid meet')
            
            if 'xmlns' not in root.attrib:
                root.set('xmlns', 'http://www.w3.org/2000/svg')
            
            clean_svg = ET.tostring(root, encoding='unicode')
            
        except ET.ParseError:
            svg_start = clean_svg.find('<svg')
            svg_end = clean_svg.find('>', svg_start)
            if svg_end != -1:
                svg_tag = clean_svg[svg_start:svg_end + 1]
                
                if 'width=' not in svg_tag:
                    svg_tag = svg_tag.replace('<svg', '<svg width="100%"')
                if 'height=' not in svg_tag:
                    svg_tag = svg_tag.replace('<svg', '<svg height="auto"')
                if 'viewBox=' not in svg_tag:
                    svg_tag = svg_tag.replace('<svg', '<svg viewBox="0 0 1200 800"')
                if 'preserveAspectRatio=' not in svg_tag:
                    svg_tag = svg_tag.replace('<svg', '<svg preserveAspectRatio="xMidYMid meet"')
                if 'xmlns=' not in svg_tag and 'xmlns:' not in svg_tag:
                    svg_tag = svg_tag.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"')
                
                clean_svg = clean_svg[:svg_start] + svg_tag + clean_svg[svg_end + 1:]
        
        # Fix common XML issues
        clean_svg = re.sub(r'<([a-zA-Z]+)([^>]*[^/])>', r'<\1\2></\1>', clean_svg)
        clean_svg = re.sub(r'&(?!(amp|lt|gt|quot|apos);)', '&amp;', clean_svg)
        
        return clean_svg
        
    except Exception as e:
        logger.error(f"Error cleaning SVG: {str(e)}")
        return '<svg width="100%" height="auto" viewBox="0 0 1200 800" xmlns="http://www.w3.org/2000/svg"><text x="100" y="100" font-size="16" fill="#000">SVG Generation Error</text></svg>'

def create_mobile_optimized_images(svg_content: str) -> Dict:
    """
    Create mobile-optimized images from SVG for React Native
    """
    try:
        clean_svg = validate_and_clean_svg(svg_content)
        
        images = {}
        
        # Preview size for React Native chat (400x300)
        try:
            png_data = cairosvg.svg2png(
                bytestring=clean_svg.encode('utf-8'),
                output_width=400,
                output_height=300,
                scale=1.0,
                unsafe=True
            )
            
            # Convert PNG to JPG for React Native
            png_image = Image.open(BytesIO(png_data))
            
            if png_image.mode in ('RGBA', 'LA', 'P'):
                white_bg = Image.new('RGB', png_image.size, (255, 255, 255))
                if png_image.mode == 'P':
                    png_image = png_image.convert('RGBA')
                white_bg.paste(png_image, mask=png_image.split()[-1] if png_image.mode == 'RGBA' else None)
                jpg_image = white_bg
            else:
                jpg_image = png_image.convert('RGB')
            
            jpg_buffer = BytesIO()
            jpg_image.save(jpg_buffer, format='JPEG', quality=85, optimize=True)
            jpg_data = jpg_buffer.getvalue()
            
            # Store as base64 for React Native
            images['jpg'] = base64.b64encode(jpg_data).decode('utf-8')
            images['png'] = base64.b64encode(png_data).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Error creating preview image: {str(e)}")
            # Create simple fallback image
            fallback_img = Image.new('RGB', (400, 300), (240, 240, 240))
            fallback_buffer = BytesIO()
            fallback_img.save(fallback_buffer, format='JPEG', quality=75)
            fallback_data = fallback_buffer.getvalue()
            images['jpg'] = base64.b64encode(fallback_data).decode('utf-8')
            images['png'] = base64.b64encode(fallback_data).decode('utf-8')
        
        # Store SVG
        images['svg'] = clean_svg
        
        return images
        
    except Exception as e:
        logger.error(f"Error in create_mobile_optimized_images: {str(e)}")
        return {
            'svg': validate_and_clean_svg(''),
            'jpg': '',
            'png': ''
        }

@app.post("/generate-svg")
async def generate_svg(
    text: str = Form(""),
    image: UploadFile = File(...)
):
    """
    Main endpoint for React Native app
    Returns JSON exactly as React Native expects
    """
    try:
        logger.info(f"📱 React Native request received")
        logger.info(f"📝 Text: {text[:100] if text else 'None'}")
        logger.info(f"🖼️ Image: {image.filename}")
        
        # Validate image
        if not image.content_type or not image.content_type.startswith('image/'):
            raise HTTPException(400, detail="File must be an image")
        
        # Read image
        image_bytes = await image.read()
        
        # Validate size (10MB max)
        MAX_SIZE = 10 * 1024 * 1024
        if len(image_bytes) > MAX_SIZE:
            raise HTTPException(400, detail="Image too large (max 10MB)")
        
        pil_image = Image.open(BytesIO(image_bytes))
        if pil_image.mode in ('RGBA', 'LA', 'P'):
            pil_image = pil_image.convert('RGB')
        
        # Prepare prompt
        full_prompt = PROMPT
        if text and text.strip():
            full_prompt = f"{PROMPT}\n\nAdditional context: {text}"
        
        logger.info("🤖 Calling Gemini...")
        
        # Call Gemini - unchanged model
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[full_prompt, pil_image],
        )
        
        svg_text = response.text
        
        if not svg_text:
            raise HTTPException(500, detail="Gemini returned empty response")
        
        logger.info(f"✅ Gemini response ({len(svg_text)} chars)")
        
        # Create images for React Native
        logger.info("🖼️ Creating images...")
        images = create_mobile_optimized_images(svg_text)
        
        # Return EXACTLY what React Native expects
        return {
            "svg": images.get('svg', ''),
            "jpg": images.get('jpg', ''),  # This is what React Native uses for preview
            "png": images.get('png', ''),
            # Optional: Add success flag
            "success": True
        }
        
    except HTTPException as he:
        logger.error(f"HTTP Exception: {he.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        # Return empty response but with proper structure for React Native
        return {
            "svg": "",
            "jpg": "",
            "png": "",
            "error": str(e)
        }

@app.post("/generate-analysis")
async def generate_analysis(
    text: str = Form(""),
    image: UploadFile = File(...)
):
    """
    Alternative endpoint with detailed response
    """
    try:
        # Same logic as generate-svg but with different response format
        image_bytes = await image.read()
        pil_image = Image.open(BytesIO(image_bytes))
        
        full_prompt = PROMPT
        if text and text.strip():
            full_prompt = f"{PROMPT}\n\nUser context: {text}"
        
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=[full_prompt, pil_image],
        )
        
        svg_text = response.text
        
        if not svg_text:
            raise HTTPException(500, detail="Empty response from Gemini")
        
        images = create_mobile_optimized_images(svg_text)
        
        return {
            "success": True,
            "message": "Analysis complete",
            "data": {
                "svg": images.get('svg', ''),
                "preview_image": images.get('jpg', ''),
                "png_image": images.get('png', '')
            }
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "Analysis failed"
        }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Business Analyzer API",
        "react_native": "compatible",
        "endpoint": "/generate-svg active"
    }

@app.get("/")
async def root():
    return {
        "message": "Business Analyzer API",
        "version": "1.0.0",
        "react_native_endpoint": "POST /generate-svg",
        "expected_response": {
            "svg": "string",
            "jpg": "base64 string",
            "png": "base64 string"
        }
    }

if __name__ == "__main__":
    logger.info("🚀 Starting Business Analyzer API for React Native")
    logger.info("📱 React Native endpoint: POST /generate-svg")
    logger.info("🤖 Using Gemini model: gemini-1.5-pro")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        log_level="info"
    )
