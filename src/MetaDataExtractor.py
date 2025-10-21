import re
import pdfplumber

class LVMetadataExtractor:
    """
    Extracts metadata from Leistungsverzeichnis (LV) PDFs such as
    project info, contractor data, and other administrative details.
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.first_page_meta = {}
        self.header_meta = []
        self.headers_first_meta = {}
        self.vorbemerkung = ""
        self.schlussbestimmung = ""

        # Define regex patterns for the first-page metadata
        self.patterns = {
            "Projekt_Name_ErsteSeite": re.compile(r"^Projekt\s*:\s*(.*)"),
            "Bauherr": re.compile(r"^Bauherr\s*:\s*(.*)"),
            "Bauantragsplanung": re.compile(r"^Bauantragsplanung\s*:\s*(.*)"),
            "Ausführungsplanung": re.compile(r"^Ausführungsplanung\s*:\s*(.*)"),
            "Bauleitung": re.compile(r"^Bauleitung\s*:\s*(.*)"),
            "Ausführungszeitraum": re.compile(r"^Ausführungszeitraum\s*:\s*(.*)"),
            "Ausführungsbeginn": re.compile(r"^Ausführungsbeginn\s*:\s*(.*)"),
            "Angebotssumme Netto": re.compile(r"^Angebotssumme Netto\s*:\s*(.*)"),
            "Mehrwertsteuer (19 %)": re.compile(r"^Mehrwertsteuer \(19 %\)\s*:\s*(.*)"),
            "Angebotssumme Brutto": re.compile(r"^Angebotssumme Brutto\s*:\s*(.*)"),
            "Angebotsabgabe": re.compile(
                r"(?si)Angebotsabgabe\s*:\s*(.*?)\s*(?=ANGEBOT\b)",
                re.DOTALL | re.IGNORECASE,
            ),
            "Bieter": re.compile(r"^Bieter\s*:\s*(.*)"),
            "LV": re.compile(r"^LV\s*:\s*(.*)"),
        }

        self.MULTILINE_FIELDS = {"Ausführungszeitraum"}

    def main(self) -> tuple:
        """main function to execute extraction steps

        Returns:
            tuple : tuple of dictionaries containing all extracted meta data
        """
        first_page_meta = self.extract_first_page_metadata()
        header_page_1 = self.extract_first_header()
        vor_schlussbemerkung = self.extract_vorbestimmung_and_schlussbestimmung(self.pdf_path)
        combined_dict = self.combine_to_dict()
        return first_page_meta, header_page_1, combined_dict, vor_schlussbemerkung

    def extract_header_metadata(self, page:int) -> dict:
        """Extract structured header info (Company, Street, Ort, Tel, Fax, E-mail, Projekt, Datum, LV)
        from a given pdfplumber page object.

        Args:
            page (int): current page

        Returns:
            dict: dictionary containing the header of a respecitve page
        """
        header_data = {}
        try:
            head_line = self._extract_header_text(page)
            header_data['total_header_data'] = self._normalize_text(head_line.split("Seite")[0].strip())
            header_text = self._normalize_text(head_line)

            parts = self._split_header_parts(header_text)
            header_data.update(self._extract_basic_info(parts))
            header_data.update(self._extract_contact_info(parts))
            header_data.update(self._extract_project_info(header_text))
            header_data.update(self._extract_lv_info(header_text))

        except Exception as e:
            print(f"Header extraction failed on page {getattr(page, 'page_number', '?')}: {e}")

        return header_data

    def _extract_header_text(self, page: int) -> str | None:
        """Extract raw header text from table or top lines.

        Args:
            page (int): respective page of pdf

        Returns:
            : _description_
        """
        tables = page.extract_tables()
        if tables and tables[0] and tables[0][0]:
            return tables[0][0][0]
        else:
            text = page.extract_text()
            return "\n".join(text.split("\n")[:6]) if text else ""

    def _normalize_text(self, text: str) -> str:
        """Normalize whitespace and remove line breaks.

        Args:
            text (str): input string to be normalized

        Returns:
            str: normalized string
        """
        return " ".join(text.split()).strip()

    def _split_header_parts(self, text: str) -> list:
        """Split header sections separated by '--'.

        Args:
            text (str): header section as string

        Returns:
            list: list containing the separatations
        """
        return [p.strip() for p in re.split(r"\s*--\s*", text) if p.strip()]

    def _extract_basic_info(self, parts: list) -> dict:
        """Extract company, street, and cleaned city (Ort).

        Args:
            parts (list): list of strings

        Returns:
            dict: dictioanry containing the information.
        """
        info = {}
        if len(parts) >= 1:
            info["Unternehmen"] = parts[0]
        if len(parts) >= 2:
            info["Straße"] = parts[1]
        if len(parts) >= 3:
            ort_candidate = re.sub(
                r"(Tel\.?:.*|Fax\.?:.*|E-?mail:.*)", "", parts[2], flags=re.IGNORECASE
            ).strip()
            info["Ort"] = ort_candidate
        return info

    def _extract_contact_info(self, parts: list) -> dict:
        """Extract Tel, Fax, and Email from all parts.

        Args:
            parts (list): list of strings

        Returns:
            dict: dictionary containing the contact information. 
        """
        info = {}
        for part in parts:
            lower = part.lower()
            if "tel" in lower:
                if m := re.search(r"Tel\.?:\s*([+\d\s/()-]+)", part):
                    info["Tel"] = m.group(1).strip()
            if "fax" in lower:
                if m := re.search(r"Fax\.?:\s*([+\d\s/()-]+)", part):
                    info["Fax"] = m.group(1).strip()
            if "@" in part:
                if m := re.search(r"([\w\.-]+@[\w\.-]+)", part):
                    info["E-mail"] = m.group(1).strip()
        return info

    def _extract_project_info(self, text: str) -> dict:
        """Extract project name and optional date.

        Args:
            text (str): input string

        Returns:
            dict: dictionary containing the name and optional date
        """
        info = {}
        proj_match = re.search(
            r"Projekt\s*:\s*(.+?)(?:\s+(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}))?(?:\s+LV:|$)",
            text,
        )
        if proj_match:
            info["Projekt_Name_Kopfzeile"] = proj_match.group(1).strip()
            if proj_match.group(2):
                info["Datum"] = proj_match.group(2).strip()
        return info

    def _extract_lv_info(self, text: str) -> dict:
        """Extract LV value.

        Args:
            text (str): input string

        Returns:
            dict: dictioanry containing the LV value
        """
        info = {}
        lv_match = re.search(r"LV\s*:\s*(.*?)\s*(?:Seite\b|$)", text, re.IGNORECASE)
        if lv_match:
            info["LV"] = lv_match.group(1).strip()
        return info


    def extract_header_from_page(self, page_number: int) -> dict:
        """Extract header info from a specific page number (1-indexed).

        Args:
            page_number (int): respective page of pdf

        Raises:
            IndexError: In case page number is out of bounds

        Returns:
            dict: containing the header_page data
        """
        with pdfplumber.open(self.pdf_path) as pdf:
            if 1 <= page_number <= len(pdf.pages):
                page = pdf.pages[page_number - 1]
                header_page = self.extract_header_metadata(page)
                return header_page
            else:
                raise IndexError(f"Page number {page_number} out of range (1–{len(pdf.pages)})")

    def extract_first_page_metadata(self) -> dict:
        """function to extract the first pages metadata.

        Returns:
            dict: returns a dictionary containing the metadata from the first page
        """
        meta = {key: "" for key in self.patterns.keys()}

        with pdfplumber.open(self.pdf_path) as pdf:
            page = pdf.pages[0]
            text = page.extract_text()
            lines = text.split("\n")

            angebot_match = self.patterns["Angebotsabgabe"].search(text)
            if angebot_match:
                angebot_value = angebot_match.group(1).strip()
                angebot_value = " ".join(
                    line.strip() for line in angebot_value.splitlines() if line.strip()
                )
                meta["Angebotsabgabe"] = angebot_value

                text = text[:angebot_match.start()] + text[angebot_match.end():]
                lines = text.split("\n")

            current_key = None
            for line in lines:
                line = line.strip()
                matched = False

                for key, pattern in self.patterns.items():
                    if key == "Angebotsabgabe":
                        continue

                    match = pattern.match(line)
                    if match:
                        value = match.group(1).strip()
                        if key == "LV":
                            lv_match = re.match(r"^(.*?)\s+Seite:", value)
                            if lv_match:
                                value = lv_match.group(1).strip()

                        meta[key] = value
                        current_key = key
                        matched = True
                        break

                if not matched and current_key in self.MULTILINE_FIELDS:
                    if line and not any(pat.match(line) for pat in self.patterns.values()):
                        meta[current_key] += " " + line

        self.first_page_meta = meta
        return meta
    
    def extract_all_headers(self) -> list:
        """Extract header info from every page of the pdf.

        Returns:
            list: list containing all header information of each page
        """
        headers = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                data = self.extract_header_metadata(page)
                if data:
                    data["Page"] = page.page_number
                    headers.append(data)
        self.header_meta = headers
        return headers

    def extract_first_header(self) -> dict:
        """Extract header info from first page.

        Returns:
            dict: containing the header info from first page
        """
        headers = self.extract_header_from_page(1)
        self.headers_first_meta = headers
        return headers

    def extract_text_from_pdf(self, file_path: str) -> str:
        """Extracts and concatenates text from all pages of the PDF.

        Args:
            file_path (str): file path

        Returns:
            str: concatenated string from all pages
        """
        with pdfplumber.open(file_path) as pdf:
            all_text = " ".join((page.extract_text() or "") for page in pdf.pages)
        # Normalize whitespace for easier regex parsing
        return " ".join(all_text.split())
    
    def clean_section_post_header(self, section_text: str, header_text: str) -> str:
        """
        Cleans a section by removing:
        - full header text
        - 'Seite' plus digits
        - table header line 'Position Menge/Einheit EP (EUR) GP (EUR)'
        
        Args:
            section_text (str): Extracted section text.
            header_text (str): Full header text to remove.
            
        Returns:
            str: Cleaned section text.
        """
        if not section_text:
            return ""
        
        cleaned_text = section_text

        # Remove the full header text
        if header_text:
            cleaned_text = re.sub(re.escape(header_text), "", cleaned_text, flags=re.IGNORECASE)

        # Remove 'Seite ' followed by digits
        cleaned_text = re.sub(r"Seite:\s*\d+", "", cleaned_text, flags=re.IGNORECASE)

        # Remove the table header line
        table_header_pattern = r"Position\s+Menge/Einheit\s+EP\s*\([A-Z]{3}\)\s+GP\s*\([A-Z]{3}\)"
        cleaned_text = re.sub(table_header_pattern, "", cleaned_text, flags=re.IGNORECASE)

        # Normalize whitespace
        cleaned_text = " ".join(cleaned_text.split())

        return cleaned_text
    
    def extract_vorbestimmung_and_schlussbestimmung(self, file_path: str) -> dict:
        """Main method to open PDF and extract both Vorbemerkung and Schlussbestimmung of the document.
        Args:
            file_path (str): path to pdf file

        Returns:
            dict: containing the Vorbemerkung and Schlussbestimmung keyed by its names
        """
        full_text = self.extract_text_from_pdf(file_path)

        self.vorbemerkung = self.extract_section_between_text(
            full_text, "Vorbemerkungen :", "AUSSCHREIBUNG"
        )
        self.vorbemerkung = self.clean_section_post_header(self.vorbemerkung, self.headers_first_meta['total_header_data'])
        self.schlussbestimmung = self.extract_section_between_text(
            full_text, "Schlussbemerkungen", "Ort, Datum"
        )
        self.schlussbestimmung = self.clean_section_post_header(self.schlussbestimmung, self.headers_first_meta['total_header_data'])
        return {
            "Vorbemerkung": self.vorbemerkung,
            "Schlussbestimmung": self.schlussbestimmung,
        }
    
    def extract_section_between_text(self, text: str, start_kw: str, end_kw: str) -> str:
        """Extracts text between two keywords within a given full-text string.
        Handles multi-page content.

        Args:
            text (str): string in which the pattern should be searched
            start_kw (str): start keyword to search for
            end_kw (str): end keyword to search for

        Returns:
            str: contains the text betweend the start and end keywords
        """
        pattern = re.compile(
            rf"{start_kw}\s*[:\-–]?\s*(.*?)(?={end_kw}\b)",
            re.IGNORECASE | re.DOTALL,
        )
        match = pattern.search(text)
        return match.group(1).strip() if match else ""

    def combine_to_dict(self) -> dict:
        """Combine extracted metadata for convenience.

        Returns:
            dict: dictionary containing various dictionaries 
            keyed by 'first_page_metadata', 'header_metadata' , 'Vorbemerkung', and 'Schlussbestimmung'
        """
        return {
            "first_page_metadata": self.first_page_meta,
            "header_metadata": self.headers_first_meta,
            "Vorbemerkung" : self.vorbemerkung,
            "Schlussbestimmung" : self.schlussbestimmung
        }
