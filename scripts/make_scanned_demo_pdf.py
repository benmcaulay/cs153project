#!/usr/bin/env python3
"""
Generate an IMAGE-ONLY (no text layer) legal PDF so the OCR fallback is required.
Synthetic data only — no real client information. Produces a two-page
"scanned" intake & medical summary whose facts ground a Demand Letter fill.
"""
import os
import random

from PIL import Image, ImageDraw, ImageFont, ImageFilter

random.seed(7)
W, H = 1700, 2200  # ~200 DPI letter
MARGIN = 150
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
body = ImageFont.truetype(FONT, 30)
bold = ImageFont.truetype(FONT_B, 30)
head = ImageFont.truetype(FONT_B, 40)

PAGE1 = [
    ("h", "STRAUS MEYERS LLP — CONFIDENTIAL CASE INTAKE"),
    ("", ""),
    ("b", "Matter: Reyes v. Brightway Logistics, Inc."),
    ("", "Case No.: 37-2024-00098123-CU-PA-CTL"),
    ("", "Court: Superior Court of California, County of San Diego"),
    ("", "Responsible Attorney: Andrew S. Meyers, Esq."),
    ("", "Adverse Party: Brightway Logistics, Inc."),
    ("", ""),
    ("b", "Client"),
    ("", "Client Name: Maria Reyes"),
    ("", "Client Address: 1840 Juniper Street, San Diego, CA 92103"),
    ("", ""),
    ("b", "The Incident"),
    ("", "Date of Incident: March 14, 2024"),
    ("", "Location: the intersection of 5th Avenue and Harbor Drive,"),
    ("", "San Diego, California."),
    ("", ""),
    ("", "On the date above, our client Maria Reyes was lawfully crossing"),
    ("", "in the marked crosswalk when a delivery truck owned and operated"),
    ("", "by Brightway Logistics, Inc. failed to yield and struck her. The"),
    ("", "driver was making a right turn against the signal. A police report"),
    ("", "was filed at the scene and a witness, Daniel Cho, provided a"),
    ("", "statement corroborating our client's account."),
    ("", ""),
    ("", "                                              — page 1 of 2 —"),
]

PAGE2 = [
    ("h", "INTAKE & MEDICAL SUMMARY (continued)"),
    ("", ""),
    ("b", "Injuries"),
    ("", "Injury Description: cervical strain and a fractured left wrist."),
    ("", "Our client also reported persistent headaches and reduced range"),
    ("", "of motion in the neck for several weeks following the collision."),
    ("", ""),
    ("b", "Treatment"),
    ("", "Treating Facility: Scripps Mercy Hospital"),
    ("", "She was transported by ambulance, underwent imaging, and the"),
    ("", "fracture was set and casted. She completed a course of physical"),
    ("", "therapy through May 2024."),
    ("", ""),
    ("b", "Damages"),
    ("", "Medical Expenses to date: $42,318.55"),
    ("", "Anticipated Future Treatment Costs: $8,500.00"),
    ("", "(estimated hardware-removal procedure and follow-up therapy)"),
    ("", ""),
    ("", "Liability is strong: signal-controlled intersection, independent"),
    ("", "witness, and a police report assigning fault to the Brightway"),
    ("", "driver. Recommend proceeding with a settlement demand."),
    ("", ""),
    ("", "                                              — page 2 of 2 —"),
]


def render(lines):
    img = Image.new("RGB", (W, H), (252, 251, 248))  # off-white, scanned feel
    d = ImageDraw.Draw(img)
    y = MARGIN
    for kind, text in lines:
        f = {"h": head, "b": bold}.get(kind, body)
        d.text((MARGIN, y), text, fill=(28, 28, 30), font=f)
        y += int(f.size * 1.5)
    # mild scanner artifacts: faint speckle + slight blur + tiny skew
    px = img.load()
    for _ in range(2500):
        x, yy = random.randint(0, W - 1), random.randint(0, H - 1)
        v = random.randint(205, 240)
        px[x, yy] = (v, v, v)
    img = img.filter(ImageFilter.GaussianBlur(0.4))
    img = img.rotate(0.3, expand=False, fillcolor=(252, 251, 248))
    return img


out_dir = "data/matters/Reyes_v_Brightway_Logistics"
os.makedirs(out_dir, exist_ok=True)
p1, p2 = render(PAGE1), render(PAGE2)
pdf_path = os.path.join(out_dir, "Reyes_intake_medical_summary_SCANNED.pdf")
p1.save(pdf_path, "PDF", resolution=200.0, save_all=True, append_images=[p2])
print("wrote", pdf_path, os.path.getsize(pdf_path), "bytes")
