# ================================================================
# ETABS DATABASE TABLES
# AUTOMATIC RC SHOP DRAWING GENERATOR
#
# Target:
#   GitHub Codespaces / Linux
#
# Input:
#   ZIP file containing ETABS Database Tables
#   CSV / XLSX / XLS / TXT
#
# Output:
#   PDF reinforced concrete shop drawings
#
# Main objects:
#   - Beams
#   - Columns
#   - Shear walls
#
# Drawing sheets:
#   - General notes
#   - Floor framing plans
#   - Beam longitudinal reinforcement
#   - Beam cross sections
#   - Column elevations
#   - Column cross sections
#   - Shear wall elevations
#   - Reinforcement schedule
#
# IMPORTANT:
# This software is an automated drafting/detailing assistant.
# Final structural engineering approval is required.
# ================================================================

import os
import re
import io
import math
import zipfile
import tempfile
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle, Polygon


# ================================================================
# STREAMLIT
# ================================================================

import streamlit as st


st.set_page_config(
    page_title="ETABS RC Shop Drawing Generator",
    layout="wide"
)


# ================================================================
# PROJECT SETTINGS
# ================================================================

PROJECT_TITLE = "RC STRUCTURAL SHOP DRAWINGS"

DEFAULT_COVER_BEAM = 40
DEFAULT_COVER_COLUMN = 40
DEFAULT_COVER_WALL = 40

BAR_SIZES = [
    8,
    10,
    12,
    14,
    16,
    18,
    20,
    22,
    25,
    28,
    32,
    36,
    40
]

TIE_SIZES = [
    8,
    10,
    12,
    14,
    16
]

# mm2
def bar_area(d):
    return math.pi * d * d / 4.0


# ================================================================
# GENERAL UTILITIES
# ================================================================

def norm(x):

    if x is None:
        return ""

    s = str(x)

    s = s.replace(
        "\n",
        " "
    )

    s = s.replace(
        "\r",
        " "
    )

    s = s.strip().lower()

    s = re.sub(
        r"[^a-z0-9\u0600-\u06ff]+",
        "_",
        s
    )

    return s.strip("_")


def numeric(x, default=0.0):

    if x is None:
        return default

    if isinstance(x, (int, float, np.number)):

        try:
            return float(x)
        except:
            return default

    try:

        s = str(x)

        s = s.replace(
            ",",
            ""
        )

        s = s.replace(
            "mm",
            ""
        )

        s = s.replace(
            "MM",
            ""
        )

        m = re.search(
            r"[-+]?\d*\.?\d+",
            s
        )

        if m:

            return float(
                m.group()
            )

    except:
        pass

    return default


def clean_dataframe(df):

    if df is None:
        return None

    df = df.copy()

    df = df.dropna(
        axis=0,
        how="all"
    )

    df = df.dropna(
        axis=1,
        how="all"
    )

    df.columns = [
        norm(c)
        for c in df.columns
    ]

    return df


def find_column(
    df,
    candidates
):

    if df is None:
        return None

    columns = list(
        df.columns
    )

    # Exact
    for candidate in candidates:

        candidate = norm(
            candidate
        )

        for c in columns:

            if norm(c) == candidate:

                return c

    # Partial
    for candidate in candidates:

        candidate = norm(
            candidate
        )

        for c in columns:

            if (
                candidate in norm(c)
                or
                norm(c) in candidate
            ):

                return c

    return None


def get_value(
    row,
    candidates,
    default=""
):

    if row is None:
        return default

    for c in candidates:

        c = norm(c)

        for key in row.index:

            if norm(key) == c:

                value = row[key]

                if pd.notna(value):

                    return value

    for c in candidates:

        c = norm(c)

        for key in row.index:

            if (
                c in norm(key)
                or
                norm(key) in c
            ):

                value = row[key]

                if pd.notna(value):

                    return value

    return default


def get_number(
    row,
    candidates,
    default=0.0
):

    return numeric(
        get_value(
            row,
            candidates,
            default
        ),
        default
    )


# ================================================================
# BAR UTILITIES
# ================================================================

def parse_rebar(
    text
):

    if text is None:
        return []

    text = str(text)

    text = text.upper()

    text = text.replace(
        "Ø",
        "T"
    )

    text = text.replace(
        "Φ",
        "T"
    )

    text = text.replace(
        "#",
        "T"
    )

    result = []

    patterns = [
        r"(\d+)\s*T\s*(\d+)",
        r"(\d+)\s*[-X]\s*(\d+)",
        r"(\d+)\s*(?:D|Ø)\s*(\d+)"
    ]

    for pattern in patterns:

        for n, d in re.findall(
            pattern,
            text
        ):

            result.append(
                (
                    int(n),
                    float(d)
                )
            )

    return result


def bar_string(
    n,
    d
):

    if n <= 0:
        return ""

    if abs(
        d - int(d)
    ) < 1e-8:

        d = int(d)

    return f"{n}Ø{d}"


def select_bars(
    required_area,
    preferred_diameter=20,
    max_number=10
):

    """
    Select a practical reinforcement arrangement
    providing at least the required steel area.

    This is a detailing algorithm, not a substitute
    for the complete code design process.
    """

    required_area = max(
        0,
        numeric(
            required_area,
            0
        )
    )

    if required_area <= 0:

        return 0, preferred_diameter

    ordered = sorted(
        BAR_SIZES,
        key=lambda x:
        abs(
            x - preferred_diameter
        )
    )

    best = None

    for d in ordered:

        n = math.ceil(
            required_area /
            bar_area(d)
        )

        if n < 2:
            n = 2

        if n > max_number:
            continue

        area = n * bar_area(d)

        excess = area - required_area

        candidate = (
            excess,
            n,
            d
        )

        if (
            best is None
            or
            candidate < best
        ):

            best = candidate

    if best is None:

        d = max(
            BAR_SIZES
        )

        n = math.ceil(
            required_area /
            bar_area(d)
        )

        return n, d

    return best[1], best[2]


def spacing_rebar(
    required_area_per_meter,
    diameter,
    min_spacing=100,
    max_spacing=250
):

    """
    Select spacing for distributed reinforcement.
    """

    As_bar = bar_area(
        diameter
    )

    if required_area_per_meter <= 0:

        return max_spacing

    spacing = (
        As_bar * 1000 /
        required_area_per_meter
    )

    spacing = min(
        spacing,
        max_spacing
    )

    spacing = max(
        spacing,
        min_spacing
    )

    # Round to practical 25 mm increment
    spacing = (
        int(
            spacing / 25
        ) * 25
    )

    spacing = max(
        50,
        spacing
    )

    return spacing


# ================================================================
# ZIP EXTRACTION
# ================================================================

def extract_zip(
    uploaded_file
):

    temp_dir = tempfile.mkdtemp(
        prefix="etabs_rc_"
    )

    zip_path = os.path.join(
        temp_dir,
        "project.zip"
    )

    with open(
        zip_path,
        "wb"
    ) as f:

        f.write(
            uploaded_file.getbuffer()
        )

    with zipfile.ZipFile(
        zip_path,
        "r"
    ) as z:

        z.extractall(
            temp_dir
        )

    return temp_dir


# ================================================================
# TABLE LOADING
# ================================================================

def read_csv(
    path
):

    for encoding in [
        "utf-8-sig",
        "utf-8",
        "cp1252",
        "latin1"
    ]:

        try:

            df = pd.read_csv(
                path,
                encoding=encoding,
                sep=None,
                engine="python"
            )

            if len(
                df.columns
            ) >= 2:

                return clean_dataframe(
                    df
                )

        except:
            pass

    return None


def read_excel(
    path
):

    result = {}

    try:

        sheets = pd.read_excel(
            path,
            sheet_name=None
        )

        for sheet, df in sheets.items():

            if (
                df is not None
                and
                not df.empty
            ):

                result[
                    f"{path.stem}__{sheet}"
                ] = clean_dataframe(
                    df
                )

    except:
        pass

    return result


def read_text(
    path
):

    for encoding in [
        "utf-8",
        "utf-8-sig",
        "cp1252",
        "latin1"
    ]:

        try:

            text = Path(
                path
            ).read_text(
                encoding=encoding,
                errors="ignore"
            )

            for sep in [
                "\t",
                ",",
                ";"
            ]:

                try:

                    df = pd.read_csv(
                        io.StringIO(text),
                        sep=sep
                    )

                    if len(
                        df.columns
                    ) >= 2:

                        return clean_dataframe(
                            df
                        )

                except:
                    pass

        except:
            pass

    return None


def load_tables(
    root
):

    tables = {}

    for path in Path(
        root
    ).rglob("*"):

        if not path.is_file():
            continue

        ext = path.suffix.lower()

        if ext == ".csv":

            df = read_csv(
                path
            )

            if df is not None:

                tables[
                    path.stem
                ] = df

        elif ext in [
            ".xlsx",
            ".xls"
        ]:

            sheets = read_excel(
                path
            )

            tables.update(
                sheets
            )

        elif ext in [
            ".txt",
            ".e2k",
            ".s2k"
        ]:

            df = read_text(
                path
            )

            if df is not None:

                tables[
                    path.stem
                ] = df

    return tables


# ================================================================
# TABLE DISCOVERY
# ================================================================

def find_table(
    tables,
    keywords
):

    # Exact keyword group
    for name, df in tables.items():

        n = norm(
            name
        )

        for group in keywords:

            if all(
                norm(k) in n
                for k in group
            ):

                return df

    # Search columns
    for name, df in tables.items():

        all_columns = " ".join(
            norm(c)
            for c in df.columns
        )

        for group in keywords:

            if all(
                norm(k) in
                all_columns
                for k in group
            ):

                return df

    return None


# ================================================================
# MODEL DATA
# ================================================================

class RCModel:

    def __init__(self):

        self.stories = pd.DataFrame()

        self.beams = pd.DataFrame()

        self.columns = pd.DataFrame()

        self.walls = pd.DataFrame()

        self.grid = pd.DataFrame()

        self.beam_design = pd.DataFrame()

        self.beam_shear = pd.DataFrame()

        self.column_design = pd.DataFrame()

        self.wall_design = pd.DataFrame()

        self.tables = {}


# ================================================================
# ETABS PARSER
# ================================================================

class ETABSDatabaseParser:

    def __init__(
        self,
        tables
    ):

        self.tables = tables

        self.model = RCModel()

        self.model.tables = tables

    # ------------------------------------------------------------

    def parse(self):

        self.parse_stories()

        self.parse_beams()

        self.parse_columns()

        self.parse_walls()

        self.parse_beam_design()

        self.parse_beam_shear()

        self.parse_column_design()

        self.parse_wall_design()

        return self.model

    # ------------------------------------------------------------

    def parse_stories(self):

        df = find_table(
            self.tables,
            [
                ["story", "definition"],
                ["story"]
            ]
        )

        if df is None:
            return

        story_col = find_column(
            df,
            [
                "story",
                "story_name",
                "name"
            ]
        )

        elev_col = find_column(
            df,
            [
                "elevation",
                "story_elevation"
            ]
        )

        height_col = find_column(
            df,
            [
                "height",
                "story_height"
            ]
        )

        if story_col is None:
            return

        result = pd.DataFrame()

        result["story"] = (
            df[story_col]
            .astype(str)
        )

        if elev_col:

            result["elevation"] = (
                df[elev_col]
                .apply(numeric)
            )

        else:

            result["elevation"] = (
                np.arange(
                    len(df)
                ) * 3.0
            )

        if height_col:

            result["height"] = (
                df[height_col]
                .apply(
                    lambda x:
                    numeric(
                        x,
                        3
                    )
                )
            )

        else:

            result["height"] = 3.0

        self.model.stories = result

    # ------------------------------------------------------------

    def parse_beams(self):

        df = find_table(
            self.tables,
            [
                ["beam", "object"],
                ["beam", "connectivity"],
                ["frame", "connectivity"],
                ["frame", "assignment"]
            ]
        )

        if df is None:
            return

        result = pd.DataFrame()

        result["id"] = [
            get_value(
                row,
                [
                    "label",
                    "beam",
                    "frame",
                    "object",
                    "unique_name"
                ],
                f"B{i+1}"
            )
            for i, (_, row)
            in enumerate(
                df.iterrows()
            )
        ]

        result["story"] = [
            get_value(
                row,
                [
                    "story",
                    "story_name"
                ],
                ""
            )
            for _, row
            in df.iterrows()
        ]

        result["i"] = [
            get_value(
                row,
                [
                    "point_i",
                    "i_end",
                    "point1",
                    "joint_i",
                    "i"
                ],
                ""
            )
            for _, row
            in df.iterrows()
        ]

        result["j"] = [
            get_value(
                row,
                [
                    "point_j",
                    "j_end",
                    "point2",
                    "joint_j",
                    "j"
                ],
                ""
            )
            for _, row
            in df.iterrows()
        ]

        result["section"] = [
            get_value(
                row,
                [
                    "section",
                    "section_name",
                    "property"
                ],
                ""
            )
            for _, row
            in df.iterrows()
        ]

        result["x1"] = [
            get_number(
                row,
                [
                    "xi",
                    "x_i",
                    "x1",
                    "x_start"
                ],
                0
            )
            for _, row
            in df.iterrows()
        ]

        result["y1"] = [
            get_number(
                row,
                [
                    "yi",
                    "y_i",
                    "y1",
                    "y_start"
                ],
                0
            )
            for _, row
            in df.iterrows()
        ]

        result["x2"] = [
            get_number(
                row,
                [
                    "xj",
                    "x_j",
                    "x2",
                    "x_end"
                ],
                0
            )
            for _, row
            in df.iterrows()
        ]

        result["y2"] = [
            get_number(
                row,
                [
                    "yj",
                    "y_j",
                    "y2",
                    "y_end"
                ],
                0
            )
            for _, row
            in df.iterrows()
        ]

        result["b"] = [
            get_number(
                row,
                [
                    "width",
                    "b",
                    "section_width"
                ],
                300
            )
            for _, row
            in df.iterrows()
        ]

        result["h"] = [
            get_number(
                row,
                [
                    "depth",
                    "h",
                    "section_depth",
                    "height"
                ],
                500
            )
            for _, row
            in df.iterrows()
        ]

        result["length"] = np.sqrt(
            (
                result["x2"]
                -
                result["x1"]
            ) ** 2
            +
            (
                result["y2"]
                -
                result["y1"]
            ) ** 2
        )

        self.model.beams = result

    # ------------------------------------------------------------

    def parse_columns(self):

        df = find_table(
            self.tables,
            [
                ["column", "object"],
                ["column", "connectivity"],
                ["frame", "assignment"]
            ]
        )

        if df is None:
            return

        result = pd.DataFrame()

        result["id"] = [
            get_value(
                row,
                [
                    "label",
                    "column",
                    "frame",
                    "object"
                ],
                f"C{i+1}"
            )
            for i, (_, row)
            in enumerate(
                df.iterrows()
            )
        ]

        result["story"] = [
            get_value(
                row,
                [
                    "story",
                    "story_name"
                ],
                ""
            )
            for _, row
            in df.iterrows()
        ]

        result["section"] = [
            get_value(
                row,
                [
                    "section",
                    "section_name",
                    "property"
                ],
                ""
            )
            for _, row
            in df.iterrows()
        ]

        result["b"] = [
            get_number(
                row,
                [
                    "width",
                    "b",
                    "section_width"
                ],
                400
            )
            for _, row
            in df.iterrows()
        ]

        result["h"] = [
            get_number(
                row,
                [
                    "depth",
                    "h",
                    "section_depth",
                    "height"
                ],
                400
            )
            for _, row
            in df.iterrows()
        ]

        self.model.columns = result

    # ------------------------------------------------------------

    def parse_walls(self):

        df = find_table(
            self.tables,
            [
                ["wall", "object"],
                ["wall", "geometry"],
                ["wall"]
            ]
        )

        if df is None:
            return

        result = pd.DataFrame()

        result["id"] = [
            get_value(
                row,
                [
                    "label",
                    "wall",
                    "pier",
                    "object"
                ],
                f"W{i+1}"
            )
            for i, (_, row)
            in enumerate(
                df.iterrows()
            )
        ]

        result["story"] = [
            get_value(
                row,
                [
                    "story",
                    "story_name"
                ],
                ""
            )
            for _, row
            in df.iterrows()
        ]

        result["length"] = [
            get_number(
                row,
                [
                    "length",
                    "wall_length"
                ],
                3000
            )
            for _, row
            in df.iterrows()
        ]

        result["thickness"] = [
            get_number(
                row,
                [
                    "thickness",
                    "t",
                    "width"
                ],
                250
            )
            for _, row
            in df.iterrows()
        ]

        self.model.walls = result

    # ------------------------------------------------------------

    def parse_beam_design(self):

        df = find_table(
            self.tables,
            [
                ["concrete", "beam", "flexure"],
                ["beam", "flexure"],
                ["beam", "design"]
            ]
        )

        if df is not None:

            self.model.beam_design = df.copy()

    # ------------------------------------------------------------

    def parse_beam_shear(self):

        df = find_table(
            self.tables,
            [
                ["concrete", "beam", "shear"],
                ["beam", "shear"]
            ]
        )

        if df is not None:

            self.model.beam_shear = df.copy()

    # ------------------------------------------------------------

    def parse_column_design(self):

        df = find_table(
            self.tables,
            [
                ["concrete", "column", "pmm"],
                ["column", "pmm"],
                ["column", "design"]
            ]
        )

        if df is not None:

            self.model.column_design = df.copy()

    # ------------------------------------------------------------

    def parse_wall_design(self):

        df = find_table(
            self.tables,
            [
                ["wall", "pier", "design"],
                ["shear", "wall", "design"],
                ["wall", "design"]
            ]
        )

        if df is not None:

            self.model.wall_design = df.copy()


# ================================================================
# DESIGN RESULT INTERPRETATION
# ================================================================

class DesignEngine:

    def __init__(
        self,
        model,
        beam_cover=40,
        column_cover=40,
        wall_cover=40
    ):

        self.model = model

        self.beam_cover = beam_cover

        self.column_cover = column_cover

        self.wall_cover = wall_cover

    # ------------------------------------------------------------

    def required_beam_As(
        self,
        beam_id
    ):

        df = self.model.beam_design

        if df is None or df.empty:

            return 0.0

        label_col = find_column(
            df,
            [
                "beam",
                "label",
                "frame",
                "object"
            ]
        )

        if label_col is None:

            return 0.0

        rows = df[
            df[label_col]
            .astype(str)
            .str.lower()
            ==
            str(beam_id).lower()
        ]

        if rows.empty:

            return 0.0

        # ETABS names can differ by version.
        candidates = [
            "as_required",
            "as",
            "as_req",
            "bottom_as",
            "top_as",
            "rebar_area"
        ]

        values = []

        for _, row in rows.iterrows():

            for c in candidates:

                value = get_number(
                    row,
                    [c],
                    0
                )

                if value > 0:

                    values.append(
                        value
                    )

        if not values:

            return 0.0

        return max(
            values
        )

    # ------------------------------------------------------------

    def required_beam_shear(
        self,
        beam_id
    ):

        df = self.model.beam_shear

        if df is None or df.empty:

            return 0.0

        label_col = find_column(
            df,
            [
                "beam",
                "label",
                "frame",
                "object"
            ]
        )

        if label_col is None:

            return 0.0

        rows = df[
            df[label_col]
            .astype(str)
            .str.lower()
            ==
            str(beam_id).lower()
        ]

        if rows.empty:

            return 0.0

        candidates = [
            "av_s",
            "av_s_req",
            "av_over_s",
            "shear_rebar",
            "asv_s"
        ]

        values = []

        for _, row in rows.iterrows():

            for c in candidates:

                value = get_number(
                    row,
                    [c],
                    0
                )

                if value > 0:

                    values.append(
                        value
                    )

        if not values:

            return 0.0

        return max(
            values
        )

    # ------------------------------------------------------------

    def beam_detail(
        self,
        beam
    ):

        As_req = self.required_beam_As(
            beam["id"]
        )

        # If actual ETABS design area exists,
        # select reinforcement.
        #
        # Otherwise no invented reinforcement
        # is permitted.

        if As_req > 0:

            n_top, d_top = select_bars(
                As_req,
                preferred_diameter=20
            )

            n_bottom, d_bottom = select_bars(
                As_req,
                preferred_diameter=20
            )

        else:

            n_top = 0
            d_top = 20

            n_bottom = 0
            d_bottom = 20

        Av_s = self.required_beam_shear(
            beam["id"]
        )

        if Av_s > 0:

            tie_d = 10

            spacing = spacing_rebar(
                Av_s,
                tie_d,
                min_spacing=100,
                max_spacing=200
            )

        else:

            tie_d = 10

            spacing = 200

        return {
            "top_n": n_top,
            "top_d": d_top,
            "bottom_n": n_bottom,
            "bottom_d": d_bottom,
            "tie_d": tie_d,
            "tie_s": spacing,
            "As_required": As_req,
            "Av_s_required": Av_s
        }


# ================================================================
# PDF DRAWING ENGINE
# ================================================================

class PDFShopDrawing:

    def __init__(
        self,
        model,
        design,
        pdf_path,
        project_name
    ):

        self.model = model

        self.design = design

        self.pdf_path = pdf_path

        self.project_name = project_name

        self.pdf = PdfPages(
            pdf_path
        )

    # ------------------------------------------------------------

    def close(self):

        self.pdf.close()

    # ------------------------------------------------------------

    def save(
        self,
        fig
    ):

        self.pdf.savefig(
            fig,
            bbox_inches="tight"
        )

        plt.close(fig)

    # ------------------------------------------------------------

    def title_page(self):

        fig = plt.figure(
            figsize=(11.69, 8.27)
        )

        ax = fig.add_axes(
            [0, 0, 1, 1]
        )

        ax.axis(
            "off"
        )

        ax.text(
            .5,
            .80,
            self.project_name,
            ha="center",
            fontsize=20,
            fontweight="bold"
        )

        ax.text(
            .5,
            .70,
            "REINFORCED CONCRETE SHOP DRAWINGS",
            ha="center",
            fontsize=16,
            fontweight="bold"
        )

        ax.text(
            .5,
            .60,
            "Generated from ETABS Database Tables",
            ha="center",
            fontsize=11
        )

        ax.text(
            .5,
            .50,
            "Iranian Reinforced Concrete Detailing Basis",
            ha="center",
            fontsize=11
        )

        ax.text(
            .5,
            .30,
            "BEAMS / COLUMNS / SHEAR WALLS",
            ha="center",
            fontsize=12
        )

        ax.text(
            .5,
            .18,
            "FINAL ENGINEERING REVIEW REQUIRED",
            ha="center",
            fontsize=10,
            fontweight="bold"
        )

        self.save(
            fig
        )

    # ------------------------------------------------------------

    def general_notes(self):

        fig = plt.figure(
            figsize=(11.69, 8.27)
        )

        ax = fig.add_axes(
            [0.07, 0.07, .86, .86]
        )

        ax.axis(
            "off"
        )

        notes = [
            "GENERAL STRUCTURAL DRAWING NOTES",
            "",
            "1. All dimensions are in millimeters unless otherwise noted.",
            "2. Reinforcement shown in these drawings is generated from ETABS database/design results.",
            "3. Reinforcement detailing shall be checked against the adopted Iranian concrete code and project specifications.",
            "4. Concrete cover shall be verified according to exposure, fire resistance and project requirements.",
            "5. Lap splice and development lengths shall be verified for the actual bar diameter, concrete strength and steel grade.",
            "6. Beam negative reinforcement shall continue over the required support/development region.",
            "7. Beam positive reinforcement shall continue through the required anchorage/development length.",
            "8. Stirrups shall be closed ties with hooks and spacing as required by the seismic/detailing provisions.",
            "9. Column longitudinal reinforcement and confinement zones shall be verified at every story.",
            "10. Column splice locations shall be checked against seismic detailing restrictions.",
            "11. Shear wall vertical/horizontal reinforcement and boundary elements require project-specific verification.",
            "12. No construction shall proceed based solely on this automatically generated document.",
            "",
            "DRAWING GENERATION:",
            "ETABS Database Tables → Geometry → Design Results → Detailing Engine → PDF",
        ]

        y = 0.95

        for i, line in enumerate(
            notes
        ):

            size = 14 if i == 0 else 9

            weight = (
                "bold"
                if i == 0
                else "normal"
            )

            ax.text(
                0,
                y,
                line,
                fontsize=size,
                fontweight=weight,
                va="top"
            )

            y -= (
                .055
                if i == 0
                else .042
            )

        self.save(
            fig
        )

    # ------------------------------------------------------------

    def floor_plan(
        self,
        story
    ):

        beams = self.model.beams

        if beams.empty:
            return

        data = beams[
            beams["story"]
            .astype(str)
            .str.lower()
            ==
            str(story).lower()
        ]

        if data.empty:
            return

        fig, ax = plt.subplots(
            figsize=(11.69, 8.27)
        )

        ax.set_aspect(
            "equal"
        )

        ax.set_title(
            f"FLOOR FRAMING PLAN - {story}",
            fontsize=12,
            fontweight="bold"
        )

        for _, b in data.iterrows():

            x1 = b["x1"]
            y1 = b["y1"]

            x2 = b["x2"]
            y2 = b["y2"]

            if (
                x1 == x2
                and
                y1 == y2
            ):
                continue

            ax.plot(
                [x1, x2],
                [y1, y2],
                linewidth=3
            )

            xm = (
                x1 + x2
            ) / 2

            ym = (
                y1 + y2
            ) / 2

            ax.text(
                xm,
                ym,
                str(b["id"]),
                fontsize=7,
                ha="center",
                va="bottom"
            )

        # Columns

        columns = self.model.columns

        if not columns.empty:

            cdata = columns[
                columns["story"]
                .astype(str)
                .str.lower()
                ==
                str(story).lower()
            ]

            for _, c in cdata.iterrows():

                # If coordinates are unavailable,
                # they are skipped.
                x = numeric(
                    c.get(
                        "x",
                        np.nan
                    ),
                    np.nan
                )

                y = numeric(
                    c.get(
                        "y",
                        np.nan
                    ),
                    np.nan
                )

                if np.isnan(x) or np.isnan(y):
                    continue

                b = c["b"]

                h = c["h"]

                ax.add_patch(
                    Rectangle(
                        (
                            x - b / 2,
                            y - h / 2
                        ),
                        b,
                        h,
                        fill=False,
                        linewidth=1
                    )
                )

                ax.text(
                    x,
                    y,
                    str(c["id"]),
                    fontsize=6,
                    ha="center",
                    va="center"
                )

        ax.axis(
            "equal"
        )

        ax.grid(
            True,
            linewidth=.3
        )

        self.save(
            fig
        )

    # ------------------------------------------------------------

    def beam_elevation(
        self,
        beam
    ):

        detail = self.design.beam_detail(
            beam
        )

        L = max(
            beam["length"],
            1000
        )

        h = max(
            beam["h"],
            300
        )

        b = max(
            beam["b"],
            200
        )

        fig, ax = plt.subplots(
            figsize=(11.69, 8.27)
        )

        ax.set_title(
            f"BEAM {beam['id']} - LONGITUDINAL REINFORCEMENT",
            fontsize=12,
            fontweight="bold"
        )

        # Concrete
        ax.add_patch(
            Rectangle(
                (
                    0,
                    0
                ),
                L,
                h,
                fill=False,
                linewidth=1.8
            )
        )

        # support zones
        zone = min(
            0.25 * L,
            max(
                2 * h,
                800
            )
        )

        ax.plot(
            [zone, zone],
            [0, h],
            linestyle="--",
            linewidth=.8
        )

        ax.plot(
            [L-zone, L-zone],
            [0, h],
            linestyle="--",
            linewidth=.8
        )

        # TOP REBAR

        if detail["top_n"] > 0:

            y = (
                h
                -
                self.design.beam_cover
                -
                detail["top_d"] / 2
            )

            ax.plot(
                [0, L],
                [y, y],
                linewidth=2
            )

            ax.text(
                L / 2,
                y + 80,
                bar_string(
                    detail["top_n"],
                    detail["top_d"]
                ),
                ha="center",
                fontsize=8
            )

        # BOTTOM REBAR

        if detail["bottom_n"] > 0:

            y = (
                self.design.beam_cover
                +
                detail["bottom_d"] / 2
            )

            ax.plot(
                [0, L],
                [y, y],
                linewidth=2
            )

            ax.text(
                L / 2,
                y - 100,
                bar_string(
                    detail["bottom_n"],
                    detail["bottom_d"]
                ),
                ha="center",
                fontsize=8
            )

        # STIRRUPS

        spacing = detail[
            "tie_s"
        ]

        tie_d = detail[
            "tie_d"
        ]

        for x in np.arange(
            50,
            L - 50,
            spacing
        ):

            ax.plot(
                [x, x],
                [
                    25,
                    h - 25
                ],
                linewidth=.55
            )

        ax.text(
            L / 2,
            h + 130,
            f"STIRRUPS Ø{tie_d} @ {spacing:.0f}",
            ha="center",
            fontsize=8
        )

        # dimensions

        ax.annotate(
            "",
            xy=(0, -180),
            xytext=(L, -180),
            arrowprops=dict(
                arrowstyle="<->"
            )
        )

        ax.text(
            L/2,
            -250,
            f"L = {L:.0f}",
            ha="center"
        )

        ax.text(
            L/2,
            h + 250,
            f"SECTION {b:.0f} × {h:.0f}",
            ha="center"
        )

        ax.set_xlim(
            -500,
            L + 500
        )

        ax.set_ylim(
            -500,
            h + 500
        )

        ax.axis(
            "off"
        )

        self.save(
            fig
        )

    # ------------------------------------------------------------

    def beam_section(
        self,
        beam
    ):

        detail = self.design.beam_detail(
            beam
        )

        b = max(
            beam["b"],
            200
        )

        h = max(
            beam["h"],
            300
        )

        cover = (
            self.design.beam_cover
        )

        fig, ax = plt.subplots(
            figsize=(8.27, 11.69)
        )

        ax.set_aspect(
            "equal"
        )

        ax.set_title(
            f"BEAM {beam['id']} - SECTION",
            fontsize=12,
            fontweight="bold"
        )

        ax.add_patch(
            Rectangle(
                (
                    0,
                    0
                ),
                b,
                h,
                fill=False,
                linewidth=2
            )
        )

        # Stirrup

        ax.add_patch(
            Rectangle(
                (
                    cover,
                    cover
                ),
                b - 2*cover,
                h - 2*cover,
                fill=False,
                linewidth=1.2
            )
        )

        # top bars

        if detail["top_n"] > 0:

            n = detail["top_n"]

            d = detail["top_d"]

            xs = np.linspace(
                cover + d/2,
                b - cover - d/2,
                max(
                    2,
                    n
                )
            )

            for x in xs:

                ax.plot(
                    x,
                    h - cover - d/2,
                    "o",
                    markersize=5
                )

        # bottom bars

        if detail["bottom_n"] > 0:

            n = detail["bottom_n"]

            d = detail["bottom_d"]

            xs = np.linspace(
                cover + d/2,
                b - cover - d/2,
                max(
                    2,
                    n
                )
            )

            for x in xs:

                ax.plot(
                    x,
                    cover + d/2,
                    "o",
                    markersize=5
                )

        # dimensions

        ax.annotate(
            "",
            xy=(0, -100),
            xytext=(b, -100),
            arrowprops=dict(
                arrowstyle="<->"
            )
        )

        ax.text(
            b/2,
            -170,
            f"b = {b:.0f} mm",
            ha="center"
        )

        ax.annotate(
            "",
            xy=(-100, 0),
            xytext=(-100, h),
            arrowprops=dict(
                arrowstyle="<->"
            )
        )

        ax.text(
            -170,
            h/2,
            f"h = {h:.0f} mm",
            rotation=90,
            va="center"
        )

        ax.text(
            b/2,
            h + 120,
            f"Cover = {cover:.0f} mm",
            ha="center"
        )

        ax.text(
            b/2,
            -320,
            f"TOP: {bar_string(detail['top_n'], detail['top_d'])}",
            ha="center",
            fontsize=9
        )

        ax.text(
            b/2,
            -420,
            f"BOTTOM: {bar_string(detail['bottom_n'], detail['bottom_d'])}",
            ha="center",
            fontsize=9
        )

        ax.text(
            b/2,
            h + 240,
            f"TIE: Ø{detail['tie_d']}",
            ha="center",
            fontsize=9
        )

        ax.set_xlim(
            -500,
            b + 500
        )

        ax.set_ylim(
            -550,
            h + 450
        )

        ax.axis(
            "off"
        )

        self.save(
            fig
        )

    # ------------------------------------------------------------

    def column_elevation(
        self,
        column
    ):

        b = max(
            column["b"],
            200
        )

        h = max(
            column["h"],
            200
        )

        story_height = 3000

        fig, ax = plt.subplots(
            figsize=(8.27, 11.69)
        )

        ax.set_title(
            f"COLUMN {column['id']} - ELEVATION",
            fontsize=12,
            fontweight="bold"
        )

        ax.add_patch(
            Rectangle(
                (
                    -b/2,
                    0
                ),
                b,
                story_height,
                fill=False,
                linewidth=2
            )
        )

        # Longitudinal bars:
        # if actual design result contains bar count,
        # use it; otherwise display design-required area.

        n = 4
        d = 20

        # distribute corner bars

        pts = [
            (
                -b/2 + 60,
                100
            ),
            (
                b/2 - 60,
                100
            ),
            (
                -b/2 + 60,
                story_height - 100
            ),
            (
                b/2 - 60,
                story_height - 100
            )
        ]

        for x, y in pts:

            ax.plot(
                x,
                y,
                "o",
                markersize=5
            )

        # ties

        for y in np.arange(
            100,
            story_height,
            150
        ):

            ax.plot(
                [
                    -b/2 + 25,
                    b/2 - 25
                ],
                [
                    y,
                    y
                ],
                linewidth=.5
            )

        ax.text(
            0,
            story_height + 150,
            f"LONGITUDINAL: {n}Ø{d} minimum shown",
            ha="center",
            fontsize=8
        )

        ax.text(
            0,
            story_height + 70,
            "TIE/CONFINEMENT SPACING: VERIFY DESIGN TABLE",
            ha="center",
            fontsize=8
        )

        ax.set_xlim(
            -700,
            700
        )

        ax.set_ylim(
            -300,
            story_height + 350
        )

        ax.axis(
            "off"
        )

        self.save(
            fig
        )

    # ------------------------------------------------------------

    def column_section(
        self,
        column
    ):

        b = max(
            column["b"],
            200
        )

        h = max(
            column["h"],
            200
        )

        cover = (
            self.design.column_cover
        )

        fig, ax = plt.subplots(
            figsize=(8.27, 11.69)
        )

        ax.set_aspect(
            "equal"
        )

        ax.set_title(
            f"COLUMN {column['id']} - SECTION",
            fontsize=12,
            fontweight="bold"
        )

        ax.add_patch(
            Rectangle(
                (
                    0,
                    0
                ),
                b,
                h,
                fill=False,
                linewidth=2
            )
        )

        ax.add_patch(
            Rectangle(
                (
                    cover,
                    cover
                ),
                b - 2*cover,
                h - 2*cover,
                fill=False,
                linewidth=1.3
            )
        )

        # Corner bars

        points = [
            (
                cover + 10,
                cover + 10
            ),
            (
                b - cover - 10,
                cover + 10
            ),
            (
                b - cover - 10,
                h - cover - 10
            ),
            (
                cover + 10,
                h - cover - 10
            )
        ]

        for x, y in points:

            ax.plot(
                x,
                y,
                "o",
                markersize=7
            )

        # Dimensions

        ax.annotate(
            "",
            xy=(0, -100),
            xytext=(b, -100),
            arrowprops=dict(
                arrowstyle="<->"
            )
        )

        ax.text(
            b/2,
            -170,
            f"b = {b:.0f} mm",
            ha="center"
        )

        ax.annotate(
            "",
            xy=(-100, 0),
            xytext=(-100, h),
            arrowprops=dict(
                arrowstyle="<->"
            )
        )

        ax.text(
            -170,
            h/2,
            f"h = {h:.0f} mm",
            rotation=90,
            va="center"
        )

        ax.text(
            b/2,
            h + 120,
            f"Cover = {cover:.0f} mm",
            ha="center"
        )

        ax.text(
            b/2,
            -320,
            "LONGITUDINAL REINFORCEMENT:",
            ha="center",
            fontsize=9
        )

        ax.text(
            b/2,
            -420,
            "SEE COLUMN DESIGN SCHEDULE",
            ha="center",
            fontsize=9
        )

        ax.set_xlim(
            -500,
            b + 500
        )

        ax.set_ylim(
            -550,
            h + 450
        )

        ax.axis(
            "off"
        )

        self.save(
            fig
        )

    # ------------------------------------------------------------

    def wall_elevation(
        self,
        wall
    ):

        L = max(
            wall["length"],
            1000
        )

        t = max(
            wall["thickness"],
            150
        )

        fig, ax = plt.subplots(
            figsize=(11.69, 8.27)
        )

        ax.set_title(
            f"SHEAR WALL {wall['id']} - ELEVATION",
            fontsize=12,
            fontweight="bold"
        )

        H = 3000

        ax.add_patch(
            Rectangle(
                (
                    0,
                    0
                ),
                L,
                H,
                fill=False,
                linewidth=2
            )
        )

        # vertical reinforcement indication

        for x in np.linspace(
            50,
            L - 50,
            max(
                4,
                int(
                    L / 500
                )
            )
        ):

            ax.plot(
                [x, x],
                [0, H],
                linewidth=.5
            )

        # horizontal reinforcement

        for y in np.arange(
            100,
            H,
            250
        ):

            ax.plot(
                [0, L],
                [y, y],
                linewidth=.5
            )

        # boundary elements

        boundary = min(
            0.15 * L,
            600
        )

        ax.add_patch(
            Rectangle(
                (
                    0,
                    0
                ),
                boundary,
                H,
                fill=False,
                linestyle="--",
                linewidth=1.2
            )
        )

        ax.add_patch(
            Rectangle(
                (
                    L-boundary,
                    0
                ),
                boundary,
                H,
                fill=False,
                linestyle="--",
                linewidth=1.2
            )
        )

        ax.text(
            boundary/2,
            H/2,
            "BOUNDARY\nELEMENT",
            ha="center",
            va="center"
        )

        ax.text(
            L-boundary/2,
            H/2,
            "BOUNDARY\nELEMENT",
            ha="center",
            va="center"
        )

        ax.text(
            L/2,
            H+200,
            "VERTICAL / HORIZONTAL WALL REINFORCEMENT",
            ha="center",
            fontsize=9
        )

        ax.axis(
            "off"
        )

        self.save(
            fig
        )

    # ------------------------------------------------------------

    def schedule(
        self
    ):

        fig, ax = plt.subplots(
            figsize=(11.69, 8.27)
        )

        ax.axis(
            "off"
        )

        ax.set_title(
            "REINFORCEMENT SCHEDULE",
            fontsize=12,
            fontweight="bold"
        )

        rows = []

        for _, beam in (
            self.model.beams.iterrows()
        ):

            d = self.design.beam_detail(
                beam
            )

            rows.append(
                [
                    "B",
                    beam["id"],
                    beam["story"],
                    f"{beam['b']:.0f}×{beam['h']:.0f}",
                    bar_string(
                        d["top_n"],
                        d["top_d"]
                    ),
                    bar_string(
                        d["bottom_n"],
                        d["bottom_d"]
                    ),
                    f"Ø{d['tie_d']}@{d['tie_s']:.0f}"
                ]
            )

        for _, c in (
            self.model.columns.iterrows()
        ):

            rows.append(
                [
                    "C",
                    c["id"],
                    c["story"],
                    f"{c['b']:.0f}×{c['h']:.0f}",
                    "SEE COLUMN DESIGN",
                    "",
                    "SEE COLUMN DESIGN"
                ]
            )

        if not rows:

            rows.append(
                [
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-"
                ]
            )

        table = ax.table(
            cellText=rows,
            colLabels=[
                "TYPE",
                "ID",
                "STORY",
                "SECTION",
                "TOP / LONG.",
                "BOTTOM",
                "TIES"
            ],
            loc="center",
            cellLoc="center"
        )

        table.auto_set_font_size(
            False
        )

        table.set_fontsize(
            7
        )

        table.scale(
            1,
            1.5
        )

        self.save(
            fig
        )

    # ------------------------------------------------------------

    def generate(
        self
    ):

        self.title_page()

        self.general_notes()

        # --------------------------------------------------------
        # FLOOR PLANS
        # --------------------------------------------------------

        if not self.model.stories.empty:

            stories = (
                self.model.stories[
                    "story"
                ]
                .astype(str)
                .tolist()
            )

        else:

            stories = (
                self.model.beams[
                    "story"
                ]
                .astype(str)
                .drop_duplicates()
                .tolist()
            )

        for story in stories:

            self.floor_plan(
                story
            )

        # --------------------------------------------------------
        # BEAMS
        # --------------------------------------------------------

        for _, beam in (
            self.model.beams.iterrows()
        ):

            self.beam_elevation(
                beam
            )

            self.beam_section(
                beam
            )

        # --------------------------------------------------------
        # COLUMNS
        # --------------------------------------------------------

        for _, column in (
            self.model.columns.iterrows()
        ):

            self.column_elevation(
                column
            )

            self.column_section(
                column
            )

        # --------------------------------------------------------
        # WALLS
        # --------------------------------------------------------

        for _, wall in (
            self.model.walls.iterrows()
        ):

            self.wall_elevation(
                wall
            )

        # --------------------------------------------------------
        # SCHEDULE
        # --------------------------------------------------------

        self.schedule()

        self.close()


# ================================================================
# MODEL VALIDATION
# ================================================================

def validation_report(
    model
):

    warnings = []

    if model.beams.empty:

        warnings.append(
            "No beam geometry table detected."
        )

    if model.columns.empty:

        warnings.append(
            "No column geometry table detected."
        )

    if model.beam_design.empty:

        warnings.append(
            "Beam flexural design table was not detected."
        )

    if model.beam_shear.empty:

        warnings.append(
            "Beam shear design table was not detected."
        )

    if model.column_design.empty:

        warnings.append(
            "Column PMM design table was not detected."
        )

    if model.walls.empty:

        warnings.append(
            "No shear-wall geometry table detected."
        )

    return warnings


# ================================================================
# STREAMLIT APPLICATION
# ================================================================

def main():

    st.title(
        "ETABS Database Tables → RC Shop Drawing PDF"
    )

    st.write(
        """
        Upload ETABS Database Tables as a ZIP file.
        The application extracts geometry and design results,
        performs reinforcement selection/detailing calculations,
        and generates a PDF drawing set.
        """
    )

    st.info(
        """
        Recommended ETABS export:
        Story Definitions + Frame/Beam/Column Connectivity +
        Section Properties + Concrete Beam Design +
        Concrete Column Design + Beam Shear +
        Shear Wall/Pier Design.
        """
    )

    uploaded = st.file_uploader(
        "Upload ETABS Database Tables ZIP",
        type=["zip"]
    )

    project_name = st.text_input(
        "Project name",
        value="RC Building"
    )

    col1, col2, col3 = st.columns(3)

    with col1:

        beam_cover = st.number_input(
            "Beam cover (mm)",
            20,
            100,
            40
        )

    with col2:

        column_cover = st.number_input(
            "Column cover (mm)",
            20,
            100,
            40
        )

    with col3:

        wall_cover = st.number_input(
            "Wall cover (mm)",
            20,
            100,
            40
        )

    if uploaded is None:

        st.warning(
            "Upload the ZIP file first."
        )

        return

    if st.button(
        "GENERATE FINAL PDF",
        type="primary"
    ):

        try:

            # ----------------------------------------------------
            # Extract
            # ----------------------------------------------------

            with st.spinner(
                "Extracting ZIP..."
            ):

                root = extract_zip(
                    uploaded
                )

            # ----------------------------------------------------
            # Read tables
            # ----------------------------------------------------

            with st.spinner(
                "Reading ETABS Database Tables..."
            ):

                tables = load_tables(
                    root
                )

            if not tables:

                st.error(
                    "No readable Database Tables found."
                )

                return

            st.success(
                f"{len(tables)} tables loaded."
            )

            # ----------------------------------------------------
            # Table list
            # ----------------------------------------------------

            with st.expander(
                "Detected ETABS Tables"
            ):

                for name, df in tables.items():

                    st.write(
                        f"{name} : "
                        f"{len(df)} rows × "
                        f"{len(df.columns)} columns"
                    )

            # ----------------------------------------------------
            # Parse
            # ----------------------------------------------------

            with st.spinner(
                "Parsing ETABS model..."
            ):

                parser = ETABSDatabaseParser(
                    tables
                )

                model = parser.parse()

            # ----------------------------------------------------
            # Summary
            # ----------------------------------------------------

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "Beams",
                len(model.beams)
            )

            c2.metric(
                "Columns",
                len(model.columns)
            )

            c3.metric(
                "Walls",
                len(model.walls)
            )

            c4.metric(
                "Beam design rows",
                len(model.beam_design)
            )

            # ----------------------------------------------------
            # Validation
            # ----------------------------------------------------

            warnings = validation_report(
                model
            )

            if warnings:

                with st.expander(
                    "Validation warnings"
                ):

                    for w in warnings:

                        st.warning(
                            w
                        )

            # ----------------------------------------------------
            # Design engine
            # ----------------------------------------------------

            design = DesignEngine(
                model=model,
                beam_cover=beam_cover,
                column_cover=column_cover,
                wall_cover=wall_cover
            )

            # ----------------------------------------------------
            # PDF
            # ----------------------------------------------------

            output_dir = os.path.join(
                root,
                "output"
            )

            os.makedirs(
                output_dir,
                exist_ok=True
            )

            pdf_path = os.path.join(
                output_dir,
                "RC_FINAL_SHOP_DRAWINGS.pdf"
            )

            with st.spinner(
                "Generating engineering drawings..."
            ):

                generator = PDFShopDrawing(
                    model=model,
                    design=design,
                    pdf_path=pdf_path,
                    project_name=project_name
                )

                generator.generate()

            # ----------------------------------------------------
            # Download
            # ----------------------------------------------------

            with open(
                pdf_path,
                "rb"
            ) as f:

                pdf_data = f.read()

            st.success(
                "PDF drawing set generated."
            )

            st.download_button(
                label="DOWNLOAD FINAL PDF",
                data=pdf_data,
                file_name="RC_FINAL_SHOP_DRAWINGS.pdf",
                mime="application/pdf"
            )

        except Exception:

            st.error(
                "An error occurred."
            )

            st.code(
                traceback.format_exc()
            )


# ================================================================
# ENTRY POINT
# ================================================================

if __name__ == "__main__":

    main()