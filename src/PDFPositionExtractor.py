import pdfplumber
import pandas as pd
import re
from src.MetaDataExtractor import LVMetadataExtractor

class PDFPositionExtractor():
    """
    Extract structured position data from a PDF containing sections, positions, quantities, and descriptions.

    This class processes multi-page PDFs, handling European numeric formats
    (dots as thousands separators, commas as decimals) and preserving
    hierarchical position information. It extracts section headers, positions,
    quantities, units, main and detailed descriptions, and section hints,
    returning a cleaned Pandas DataFrame ready for analysis.

    Attributes:
        pdf_path (str): Path to the PDF file to extract.
    """
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.rows = []
        self.section = None
        self.current = None
        self.section_hint = ""
        self.datatypes = {
                            'Section': 'string',
                            'SectionHint': 'string',
                            'MainDescription': 'string',
                            'DetailedDescription': 'string',
                            'Quantity': float,
                            'Unit': 'string',           
                            'Page': 'int32',
                            'Position': 'string'
                        }

        # Precompile regex patterns
        self.pos_pattern = re.compile(r"^(\d+\.\.\.\d+)\s+(.*)")
        self.qty_pattern = re.compile(r"^([\d.]+(?:,\d+)?)\s+(\S+)")
        self.section_pattern = re.compile(r"^(\d+)\s+([A-Za-zÄÖÜäöüß\s\-]+)$")
        self.metadata_header = LVMetadataExtractor(self.pdf_path).extract_first_header()


    def main(self) -> pd.DataFrame:
        """Execute the full PDF extraction and processing pipeline.

        This method runs the following steps sequentially:
            - Extract raw content from the PDF
            - Generate position levels for hierarchical analysis
            - Apply individual cleaning rules
            - Parse columns into appropriate data types and normalize numbers
            - Fill hint columns

        Returns:
            pd.DataFrame: _description_
        """
        df = self.extract()
        df = self.generate_position_levels(df=df)
        df = self.cleaning_steps(df=df)
        df = self.parse_datatypes(df=df)
        df = self.fill_hint_columns(df=df)
        return df
    
    def fill_hint_columns(self, df:pd.DataFrame) -> pd.DataFrame:
        df['SectionHint'] = df.groupby('position_level_1')['SectionHint'].transform(lambda x: x.ffill().bfill())
        return df
        
    def generate_position_levels(self, df:pd.DataFrame, position_column:str = 'Position', postion_datatype:str='int32') -> pd.DataFrame:
        """
        Generate hierarchical position levels from a position identifier column.

        This method splits the `position_column` (e.g., "1...3") into:
            - position_level_1: the first segment (main position)
            - position_level_2: the last segment (sub-position)
        and converts them to the specified numeric datatype.
        """
        df['position_level_1'] = df[position_column].str.split('.').str[0].astype(postion_datatype)
        df['position_level_2'] = df[position_column].str.split('.').str[-1].astype(postion_datatype)
        return df 
    
    def cleaning_steps(self, df:pd.DataFrame) -> pd.DataFrame:
        """Apply individual cleaning rules to the extracted DataFrame.

        Current cleaning rules:
            - Replace placeholder text with NaN
            - Clear specific strings in SectionHint values
        """
        df.replace(['___ ________ ____________','________'], pd.NA, inplace=True)
        replace_indices = df[df['SectionHint'].str.startswith('Ingenieurbüro Wagner und Koll')==True].index
        df.loc[replace_indices, 'SectionHint'] = pd.NA
        return df
    
    def parse_datatypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert columns in the DataFrame to their defined datatypes and normalize numeric values.

        Args:
            df (pd.DataFrame): input DataFrame

        Returns:
            pd.DataFrame: _description_
        """        
        
        # Normalize Quantity column
        if "Quantity" in df.columns:
            df["Quantity"] = df["Quantity"].apply(self._normalize_number)
            df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
        
        # Apply all other datatypes defined in self.datatypes
        df = df.astype(self.datatypes, errors="ignore")
        
        return df

    def extract(self) -> pd.DataFrame:
        """Extract structured position data from a PDF into a Pandas DataFrame.

        This method opens the PDF specified by `self.pdf_path` in the init function, iterates through all pages,
        and extracts lines of text. It processes each line to identify sections, positions,
        quantities, units, detailed descriptions, and section hints using the `_process_lines` method.

        The method supports:
            - Multi-page PDFs with continuation of positions or descriptions across pages
            - Handling missing or empty pages
            - Accurate assignment of page numbers to each position

        After processing all pages, the collected rows are converted into a Pandas DataFrame.

        Args:
            None

        Returns:
            pd.DataFrame: A DataFrame containing the extracted position data with columns:
                - Section: str, the section name
                - SectionHint: str or None, any additional section information
                - Position: str, the position identifier
                - MainDescription: str, main description of the position
                - DetailedDescription: str, detailed description of the position
                - Quantity: str or numeric, the quantity (raw string; can be normalized later)
                - Unit: str, the unit of the quantity
                - Page: int, the page number in the PDF where the position appears
        """
        with pdfplumber.open(self.pdf_path) as pdf:
            num_pages = len(pdf.pages)
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                if not text:
                    continue
                lines = text.split('\n')
                # Mark last page correctly
                is_last = i == num_pages
                self._process_lines(lines, page.page_number, is_last_page=is_last)
        
        # Convert collected rows into DataFrame
        df = pd.DataFrame(self.rows)
        return df
    
    def _process_lines(self, lines: list[str], page_number: int, is_last_page: bool = False) -> None:
        """Process each line of a PDF page to extract structured position data.

        This function iterates through all lines on a page and delegates processing to specialized helper methods:
            - Section headers
            - Position entries
            - Quantity/unit lines
            - Section hints
            - Detailed descriptions

        At the end of the page (or for the last page), it finalizes any currently open position and appends it to the collected rows.

        Args:
            lines (list[str]): List of strings representing lines extracted from a PDF page.
            page_number (int): The current page number being processed.
            is_last_page (bool, optional): If True, ensures the last open position is finalized.
                                            Defaults to False.

        Returns:
            None: The function updates self.rows and self.current in place.
        """
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Try each type of line in priority order
            if self._process_section_header(line):
                continue
            if self._process_position(line, page_number):
                continue
            if self._process_quantity_unit(line):
                continue
            if self._process_section_hint(line):
                continue
            self._process_detailed_description(line)

        # Save the last position at the end of the page
        if is_last_page:
            self._finalize_current_position()


    def _process_section_header(self, line: str) -> bool:
        """Detect and process a section header line.

        If a section header is detected, finalizes any open position, updates the current section, and clears section hints.

        Args:
            line (str): A single line of text from the PDF.

        Returns:
            bool: True if the line was a section header and processed, else False.
        """
        sec_match = self.section_pattern.match(line)
        if not sec_match:
            return False
        self._finalize_current_position()
        self.section = sec_match.group(2).strip()
        self.section_hint = ""
        return True

    def _process_position(self, line: str, page_number: int) -> bool:
        """Detect and process a new position line.

        Finalizes any open position, creates a new current position dictionary with default fields, and clears section hints.

        Args:
            line (str): A single line of text from the PDF.
            page_number (int): The current page number being processed.

        Returns:
            bool: True if the line represents a new position, else False.
        """
        pos_match = self.pos_pattern.match(line)
        if not pos_match:
            return False
        self._finalize_current_position()
        self.current = {
            "Section": self.section,
            "SectionHint": self.section_hint.strip() if self.section_hint else None,
            "Position": pos_match.group(1),
            "MainDescription": pos_match.group(2).strip(),
            "DetailedDescription": "",
            "Quantity": None,
            "Unit": None,
            "Page": page_number
        }
        self.section_hint = ""
        return True

    def _process_quantity_unit(self, line: str) -> bool:
        """Detect and process a quantity/unit line for the current position.

        If a quantity/unit line is matched, stores the raw quantity and unit in self.current.

        Args:
            line (str): A single line of text from the PDF.

        Returns:
            bool: True if the line was a quantity/unit line, else False.
        """
        qty_match = self.qty_pattern.match(line)
        if not qty_match or not self.current:
            return False
        self.current["Quantity"] = qty_match.group(1)
        self.current["Unit"] = qty_match.group(2)
        return True

    def _process_section_hint(self, line:str) -> bool:
        """Accumulate section hints when no position is currently open.

        Args:
            line (str): A single line of text from the PDF.

        Returns:
            bool: True if the line was treated as a section hint, else False.
        """
        if self.section and not self.current:
            self.section_hint = (self.section_hint + " " + line).strip() if self.section_hint else line
            return True
        return False

    def _process_detailed_description(self, line:str):
        """Append line to the detailed description of the current position.

        Skips lines containing known irrelevant strings like "Übertrag", "Summe", "mailto:", or "Projekt:".
        (We don't drop lines just because they contain the header/Seite text — we remove those fragments later.)

        Args:
            line (str): string containing the content within a line
        """
        skip_tokens = ["Übertrag", "Summe", "mailto:", "Projekt:"]
        if not self.current:
            return

        # If the line is entirely one of the skip tokens, skip it
        if any(line.startswith(tok) for tok in skip_tokens):
            return

        # Append the line (preserve content; we'll clean later)
        if self.current["DetailedDescription"]:
            self.current["DetailedDescription"] += " " + line
        else:
            self.current["DetailedDescription"] = line

    def _clean_detailed_description(self, desc: str) -> str:
        """Remove 'Übertrag', company blocks ending with EP/GP footer, and company → ZUSAMMENFASSUNG."""
        if not desc:
            return desc

        s = desc

        # Remove Übertrag block as before
        s = re.sub(
            r"Ü+\s*b+e+r+t+r+a+g+[:]*.*?EP\s*\(EUR\)\s*GP\s*\(EUR\)",
            " ",
            s,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # Remove block starting with 'Unternehmen' from metadata, ending with EP/GP footer
        if hasattr(self, "metadata_header"):
            unternehmen = self.metadata_header.get("Unternehmen")
            if unternehmen:
                company_pattern = re.escape(unternehmen)
                company_pattern = company_pattern.replace(r"\ ", r"\s*")
                pattern = rf"{company_pattern}.*?EP\s*\(EUR\)\s*GP\s*\(EUR\)"
                s = re.sub(pattern, " ", s, flags=re.IGNORECASE | re.DOTALL)

        # Remove block starting with 'Unternehmen Name' and ending with ZUSAMMENFASSUNG
        if hasattr(self, "metadata_header"):
            unternehmen = self.metadata_header.get("Unternehmen")
            if unternehmen:
                company_pattern = re.escape(unternehmen)
                company_pattern = company_pattern.replace(r"\ ", r"\s*")
                pattern = rf"{company_pattern}.*?Firmenstempel, rechtsverbindliche Unterschrift"
                s = re.sub(pattern, " ", s, flags=re.IGNORECASE | re.DOTALL)

        # Cleanup leftover whitespace
        s = re.sub(r"\s+", " ", s).strip()

        return s

    def _finalize_current_position(self):
        if self.current:
            if self.current.get("DetailedDescription"):
                self.current["DetailedDescription"] = self._clean_detailed_description(
                    self.current["DetailedDescription"]
                )
                if not self.current["DetailedDescription"]:
                    self.current["DetailedDescription"] = None
            self.rows.append(self.current)
            self.current = None


    def _normalize_number(self, value):
        """Normalize European-style numbers to a Python float-compatible string.

        European PDFs often represent numbers with:
            - Dots (.) as thousands separators
            - Commas (,) as decimal separators
        This function converts such numbers into a standard Python format
        suitable for `float()` or `pd.to_numeric()` conversion.

        The function handles:
            - Numbers with commas as decimal separators (e.g., "3.350,50" → "3350.50")
            - Numbers with dots as thousands separators (e.g., "3.350.000" → "3350000")
            - Numbers with a single dot as decimal (e.g., "1234.50" → "1234.50")
            - Numbers with spaces as thousands separators (e.g., "1 234,75" → "1234.75")
            - Missing values (NaN) are returned unchanged

        Args:
            value (str | int | float | None): The input number, typically extracted from a PDF.
                - Can be a string with European formatting
                - Can be numeric (int/float)
                - Can be None or NaN

        Returns:
            str: A string representing the number in standard Python float format:
                - Decimal point as dot (.)
                - No thousands separators
                - Suitable for conversion to float
        """
        if pd.isna(value):
            return value
        if not isinstance(value, str):
            value = str(value)
        value = value.strip()

        # Case 1: contains comma → last comma is decimal separator
        if ',' in value:
            parts = value.rsplit(',', 1)  # split only on last comma
            int_part = parts[0].replace('.', '').replace(' ', '')
            decimal_part = parts[1]
            value = f"{int_part}.{decimal_part}"
        else:
            # No comma → if last dot looks like decimal (≤ 2 digits), keep it; else all dots are thousands separators
            if '.' in value:
                parts = value.rsplit('.', 1)
                if len(parts[-1]) <= 2:
                    int_part = parts[0].replace('.', '').replace(' ', '')
                    decimal_part = parts[1]
                    value = f"{int_part}.{decimal_part}"
                else:
                    value = value.replace('.', '').replace(' ', '')
        return value


