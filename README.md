# ETABS-RC-Shop-Drawing-Generator

An automated structural detailing tool that extracts reinforced concrete design and geometry data from **ETABS Database Tables** and generates preliminary **reinforced concrete shop drawings in PDF format**.

The application is designed to assist structural engineers in converting ETABS analysis/design results into organized reinforcement drawings for beams, columns, and shear walls.

## Features

* Import ETABS Database Tables from a ZIP file
* Support for CSV, XLSX, and TXT table formats
* Automatic detection of ETABS structural and design tables
* Reinforced concrete beam detailing
* Beam top and bottom reinforcement visualization
* Beam stirrup detailing
* Beam cross-sections
* Column reinforcement visualization
* Column longitudinal reinforcement and ties
* Shear wall reinforcement visualization
* Floor plan generation
* Reinforcement schedules
* Automatic PDF drawing generation
* Streamlit web-based interface
* Designed to run in GitHub Codespaces
* No ETABS installation required for the drawing-generation stage

## Project Structure

```text
ETABS-RC-Shop-Drawing/
│
├── app.py
├── requirements.txt
└── README.md
```

## Requirements

The project requires Python 3.11 or a compatible Python version.

Main Python packages:

```text
streamlit
pandas
numpy
matplotlib
openpyxl
xlrd
```

Install all dependencies with:

```bash
pip install -r requirements.txt
```

## Running the Application

Start the Streamlit application with:

```bash
python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

In GitHub Codespaces, open port **8501** to access the web application.

## Input Data

The application expects an ETABS Database Tables export packaged as a ZIP file.

The ZIP file can contain ETABS tables in formats such as:

```text
.csv
.xlsx
.xls
.txt
```

Typical information extracted from the tables includes:

* Story definitions
* Beam geometry
* Column geometry
* Shear wall geometry
* Beam reinforcement design results
* Column reinforcement design results
* Wall reinforcement/design information

## Workflow

The general workflow is:

```text
ETABS Model
     │
     ▼
ETABS Database Tables
     │
     ▼
Export Tables
     │
     ▼
ZIP File
     │
     ▼
ETABS RC Shop Drawing Generator
     │
     ├── Geometry Extraction
     ├── Design Data Extraction
     ├── Reinforcement Processing
     ├── Detailing
     └── Drawing Generation
     │
     ▼
PDF Shop Drawing
```

## Generated Drawings

The application can generate PDF sheets containing:

### Floor Plans

Floor plans showing the structural elements detected from ETABS tables.

### Beam Drawings

Beam drawings may include:

* Beam identification
* Beam length
* Beam width and depth
* Top reinforcement
* Bottom reinforcement
* Stirrup reinforcement
* Support reinforcement
* Span reinforcement
* Beam cross-sections

Example reinforcement notation:

```text
3Ø16 TOP
3Ø16 BOTTOM
Ø10 @ 10 cm
Ø10 @ 20 cm
```

### Column Drawings

Column drawings may include:

* Column identification
* Column dimensions
* Longitudinal reinforcement
* Transverse reinforcement
* Column elevation
* Column cross-section

### Shear Walls

Where suitable ETABS wall data are available, the application can generate preliminary wall elevations and reinforcement representations.

### Reinforcement Schedule

A reinforcement schedule can be generated to organize the reinforcement information extracted from the ETABS model.

## Iranian Concrete Code

The project is intended to support reinforced concrete detailing workflows based on the principles of **Iranian Concrete Code, Chapter 9 (مبحث نهم)**.

However, the current implementation should be considered an **engineering detailing assistant**, not a replacement for professional engineering review.

Important project-specific requirements such as:

* Minimum reinforcement
* Maximum reinforcement
* Development length
* Lap splice length
* Seismic detailing
* Stirrup confinement zones
* Hook requirements
* Beam-column joint detailing
* Column confinement
* Shear wall boundary elements
* Construction joints
* Anchorage requirements

must be verified by the responsible structural engineer according to the applicable edition of the Iranian code and project requirements.

## Important Note

The generated drawings are currently intended as **preliminary/automated detailing outputs**.

The software does not replace:

* Structural engineering judgment
* ETABS model verification
* Code checking
* Construction documentation review
* Engineer approval
* Project-specific detailing requirements

The final construction drawings must be reviewed and approved by a qualified structural engineer.

## Why ETABS Database Tables?

The application works directly with ETABS Database Tables instead of requiring direct communication with the ETABS API.

This provides several advantages:

* No ETABS installation is required to generate drawings
* The workflow can run in GitHub Codespaces
* ETABS data can be processed using Python
* The project can be developed as an independent open-source tool
* The system can potentially support multiple ETABS versions
* The drawing-generation process can be automated

## GitHub Codespaces

To run the project in GitHub Codespaces:

```bash
git clone https://github.com/Ghorbanpoor/ETABS-RC-Shop-Drawing-Generator.git
cd ETABS-RC-Shop-Drawing

python -m pip install --upgrade pip
pip install -r requirements.txt

python -m streamlit run app.py \
    --server.address 0.0.0.0 \
    --server.port 8501
```

Then open the forwarded port **8501** in Codespaces.

## Future Development

Planned improvements include:

* More accurate ETABS Database Table recognition
* Full Iranian Chapter 9 reinforcement checks
* Improved seismic detailing
* Automatic development and lap-length calculation
* Beam-column joint detailing
* More accurate shear wall boundary-element detailing
* Foundation reinforcement drawings
* Stair reinforcement drawings
* DXF/DWG export
* Automatic bar bending schedules
* Rebar numbering
* Multi-sheet engineering drawing sets
* Automatic dimensioning
* Improved PDF layout
* Support for ACI 318
* Support for Eurocode 2
* Integration with ETABS API
* AI-assisted drawing quality control

## Disclaimer

This software is provided for engineering research, automation, and preliminary detailing purposes. The generated drawings should not be used for construction without verification and approval by a qualified structural engineer.

## License

This project can be released under an open-source license such as the **MIT License**.

---

**ETABS RC Shop Drawing Generator**
Automating the workflow from ETABS Database Tables to reinforced concrete shop drawings.
