"""
Engineering report generation.

Packages already-computed terrain/hydrology analysis results (elevation,
slope, flow direction/accumulation, streams, watershed, flood
susceptibility) into a downloadable PDF summary. This module performs NO
new analysis - it only formats results that were already computed
elsewhere in the pipeline.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from fpdf import FPDF


# Susceptibility fraction above which a field-verification recommendation
# is triggered. This is a simple, transparent rule of thumb - not a
# calibrated engineering threshold.
HIGH_SUSCEPTIBILITY_FLAG_FRACTION = 0.15


@dataclass
class ReportInputs:
    project_name: str
    study_area: str
    dem_file_name: str
    used_conditioned: bool
    dem_analysis: Any
    slope_aspect_result: Any
    flow_direction_result: Any
    flow_accumulation_result: Any
    stream_result: Optional[Any] = None
    susceptibility_result: Optional[Any] = None
    catchment_result: Optional[Any] = None
    catchment_pour_point: Optional[tuple[int, int]] = None
    # Maps of figure key -> PNG bytes, e.g. {"elevation": b"...", "slope": b"..."}.
    # Keys expected: elevation, slope, flow_accumulation, streams, catchment,
    # susceptibility. Missing keys simply skip that image - not an error.
    images: dict[str, bytes] = field(default_factory=dict)


class _ReportPDF(FPDF):
    def header(self) -> None:  # noqa: D102 - FPDF hook
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "GeoDrainAI - Engineering Report", ln=True)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(110, 110, 110)
        self.cell(0, 6, datetime.now().strftime("Generated %Y-%m-%d %H:%M"), ln=True)
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def footer(self) -> None:  # noqa: D102 - FPDF hook
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(130, 130, 130)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def _section_title(pdf: FPDF, title: str) -> None:
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(235, 235, 240)
    pdf.cell(0, 8, title, ln=True, fill=True)
    pdf.ln(1)


def _kv_row(pdf: FPDF, label: str, value: str) -> None:
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(60, 6, label)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, value, ln=True)


def _body_text(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 5.5, text)
    pdf.ln(1)


def _add_image(pdf: FPDF, image_bytes: Optional[bytes], caption: str) -> None:
    """Embed a PNG (as bytes) into the report, best-effort. Skips silently
    if image_bytes is None or embedding fails, so a missing/broken figure
    never breaks the rest of the report."""
    if not image_bytes:
        return
    try:
        pdf.image(io.BytesIO(image_bytes), w=170)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(130, 130, 130)
        pdf.cell(0, 5, caption, ln=True, align="C")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)
    except Exception:  # noqa: BLE001 - images are best-effort
        pass


def build_pdf_report(inputs: ReportInputs) -> bytes:
    """Build the engineering report PDF and return it as raw bytes."""

    pdf = _ReportPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # --- Project summary ---------------------------------------------
    _section_title(pdf, "Project Summary")
    _kv_row(pdf, "Project name:", inputs.project_name or "Unnamed Project")
    _kv_row(pdf, "Study area:", inputs.study_area or "Not specified")
    _kv_row(pdf, "Source DEM file:", inputs.dem_file_name or "Unknown")
    _kv_row(
        pdf,
        "Elevation used:",
        "Sink-filled (conditioned)" if inputs.used_conditioned else "Raw (unconditioned)",
    )
    pdf.ln(3)

    # --- Elevation ------------------------------------------------------
    da = inputs.dem_analysis
    _section_title(pdf, "Elevation Statistics")
    _kv_row(pdf, "Min elevation (m):", f"{da.min_elevation:.2f}")
    _kv_row(pdf, "Max elevation (m):", f"{da.max_elevation:.2f}")
    _kv_row(pdf, "Mean elevation (m):", f"{da.mean_elevation:.2f}")
    _kv_row(pdf, "Elevation range (m):", f"{da.elevation_range:.2f}")
    _kv_row(pdf, "Grid size (rows x cols):", f"{da.rows} x {da.columns}")
    _kv_row(pdf, "CRS:", str(da.crs))
    _kv_row(pdf, "Resolution (x, y):", f"{da.resolution_x:.3f}, {da.resolution_y:.3f}")
    pdf.ln(3)
    _add_image(pdf, inputs.images.get("elevation"), "Elevation map")

    # --- Slope ------------------------------------------------------
    slope_stats = inputs.slope_aspect_result.summary_statistics()
    _section_title(pdf, "Slope Statistics")
    _kv_row(pdf, "Mean slope (deg):", f"{slope_stats['mean_slope_degrees']:.2f}")
    _kv_row(pdf, "Median slope (deg):", f"{slope_stats['median_slope_degrees']:.2f}")
    _kv_row(pdf, "Max slope (deg):", f"{slope_stats['max_slope_degrees']:.2f}")
    _kv_row(pdf, "Std dev slope (deg):", f"{slope_stats['std_slope_degrees']:.2f}")
    pdf.ln(3)
    _add_image(pdf, inputs.images.get("slope"), "Slope map")

    # --- Flow direction ------------------------------------------------
    fd_stats = inputs.flow_direction_result.summary_statistics()
    _section_title(pdf, "Flow Direction (D8) Statistics")
    _kv_row(pdf, "Defined direction:", f"{fd_stats['defined_direction_fraction'] * 100:.1f}%")
    _kv_row(pdf, "Sink cells:", f"{fd_stats['sink_count']:,}")
    _kv_row(pdf, "Flat cells:", f"{fd_stats['flat_count']:,}")
    pdf.ln(3)

    # --- Flow accumulation -----------------------------------------
    fa_stats = inputs.flow_accumulation_result.summary_statistics()
    _section_title(pdf, "Flow Accumulation Statistics")
    _kv_row(pdf, "Max accumulation (cells):", f"{fa_stats['max_accumulation']:,}")
    _kv_row(pdf, "Mean accumulation (cells):", f"{fa_stats['mean_accumulation']:.2f}")
    pdf.ln(3)
    _add_image(pdf, inputs.images.get("flow_accumulation"), "Flow accumulation map (log scale)")

    # --- Streams ------------------------------------------------------
    if inputs.stream_result is not None:
        stream_stats = inputs.stream_result.summary_statistics()
        _section_title(pdf, "Stream Network Extraction")
        _kv_row(pdf, "Stream cells:", f"{stream_stats['stream_cell_count']:,}")
        _kv_row(pdf, "Stream fraction:", f"{stream_stats['stream_fraction'] * 100:.2f}%")
        _kv_row(pdf, "Accumulation threshold:", f"{stream_stats['threshold_value']:.1f}")
        _body_text(
            pdf,
            "Streams are a raster classification (cells above a flow-"
            "accumulation percentile threshold), not a connected vector "
            "stream network.",
        )
        pdf.ln(2)
        _add_image(pdf, inputs.images.get("streams"), "Stream network map")

    # --- Watershed / catchment -------------------------------------
    if inputs.catchment_result is not None:
        _section_title(pdf, "Watershed / Catchment Delineation")
        if inputs.catchment_pour_point is not None:
            row, col = inputs.catchment_pour_point
            _kv_row(pdf, "Pour point (row, col):", f"({row}, {col})")
        _kv_row(pdf, "Catchment cells:", f"{inputs.catchment_result.cell_count:,}")
        _kv_row(
            pdf,
            "Catchment area:",
            f"{inputs.catchment_result.area:.6g} (map units squared)",
        )
        _body_text(
            pdf,
            "This is a single delineated catchment for the selected pour "
            "point, not an automatic whole-DEM basin segmentation.",
        )
        pdf.ln(2)
        _add_image(pdf, inputs.images.get("catchment"), "Delineated catchment map")

    # --- Flood susceptibility -----------------------------------------
    if inputs.susceptibility_result is not None:
        sus_stats = inputs.susceptibility_result.summary_statistics()
        total = sus_stats["valid_cell_count"]
        high_fraction = sus_stats["high_fraction"]

        _section_title(pdf, "Flood Susceptibility Indicator")
        _kv_row(
            pdf,
            "Low susceptibility:",
            f"{sus_stats['low_count']:,} ({sus_stats['low_count'] / total * 100:.1f}%)",
        )
        _kv_row(
            pdf,
            "Moderate susceptibility:",
            f"{sus_stats['moderate_count']:,} "
            f"({sus_stats['moderate_count'] / total * 100:.1f}%)",
        )
        _kv_row(
            pdf,
            "High susceptibility:",
            f"{sus_stats['high_count']:,} ({high_fraction * 100:.1f}%)",
        )
        pdf.ln(2)
        _add_image(pdf, inputs.images.get("susceptibility"), "Flood susceptibility map")

        _body_text(
            pdf,
            "SCOPE NOTE: this is a terrain-based susceptibility screening "
            "indicator, not a validated flood-risk model. It combines "
            "slope, flow accumulation, and stream proximity using equal, "
            "assumption-based weights. It does NOT use rainfall, soil, or "
            "land-use data and has not been calibrated against any "
            "observed flood record. For screening/discussion only; any "
            "real decision requires engineering validation.",
        )

        _section_title(pdf, "Preliminary Recommendation")
        if high_fraction >= HIGH_SUSCEPTIBILITY_FLAG_FRACTION:
            _body_text(
                pdf,
                f"High-susceptibility terrain covers {high_fraction * 100:.1f}% "
                "of the analyzed area, which exceeds the "
                f"{HIGH_SUSCEPTIBILITY_FLAG_FRACTION * 100:.0f}% screening "
                "threshold used here. Recommend field verification and a "
                "detailed hydraulic study (rainfall-runoff and hydraulic "
                "modeling) before any drainage infrastructure or siting "
                "decision in this area."
            )
        else:
            _body_text(
                pdf,
                f"High-susceptibility terrain covers {high_fraction * 100:.1f}% "
                "of the analyzed area, below the screening threshold used "
                "here. No elevated terrain-based concern identified by this "
                "screening pass; standard due diligence still applies for "
                "any infrastructure decision."
            )

    # --- Closing disclaimer -----------------------------------------
    pdf.ln(4)
    _section_title(pdf, "Disclaimer")
    _body_text(
        pdf,
        "This report presents terrain and hydrology ANALYSIS output only. "
        "Results are not engineering-certified and must be reviewed by a "
        "qualified engineer before use in any drainage design decision."
    )

    return bytes(pdf.output())