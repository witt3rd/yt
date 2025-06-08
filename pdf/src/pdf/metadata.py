"""PDF metadata generation for enhanced conversion output.

This module provides functionality to extract metadata from converted PDF content
and generate AI-powered filenames, tags, and frontmatter for Obsidian-compatible
markdown output.
"""

import re
from dataclasses import dataclass
from urllib.parse import urlparse
from typing import Any, override

from loguru import logger

from common.config import Config
from common.ai_metadata import (
    AIMetadataGenerator,
    AIGeneratedContent,
    MetadataGenerationError,
    sanitize_filename,
)
from .converter import ConvertedContent


@dataclass
class PdfMetadata:
    """PDF content metadata structure.

    Parameters
    ----------
    url : str
        Original URL or file path of the PDF.
    title : str, optional
        Document title extracted from content.
    description : str, optional
        Document description or abstract if available.
    author : str, optional
        Author name extracted from content.
    publish_date : str, optional
        Publication date in YYYY-MM-DD format if available.
    conversion_date : str
        Date when content was converted in ISO format.
    content_type : str
        Type of content (research_paper, document, manual, etc.).
    word_count : int
        Word count of the content.
    source_type : str
        Source type (file, arxiv, url).
    pages : int
        Number of pages in the PDF.
    language : str
        Document language detected by Marker.
    """

    url: str
    title: str | None
    description: str | None
    author: str | None
    publish_date: str | None
    conversion_date: str
    content_type: str
    word_count: int
    source_type: str
    pages: int
    language: str


class PdfMetadataGenerator(AIMetadataGenerator):
    """Generate PDF content metadata and AI-powered enhancements.

    Provides methods to extract metadata from converted PDF content and generate
    AI-powered filenames, tags, and authors using OpenAI for enhanced
    markdown output with Obsidian-compatible frontmatter.

    Parameters
    ----------
    config : Config, optional
        Configuration instance. If None, creates a new Config instance.

    Examples
    --------
    >>> generator = PdfMetadataGenerator()
    >>> content = ConvertedContent(...)
    >>> metadata = generator.extract_pdf_metadata(content)
    >>> metadata.title
    "Attention Is All You Need"
    """

    def __init__(self, config: Config | None = None):
        """Initialize PDF metadata generator.

        Parameters
        ----------
        config : Config, optional
            Configuration instance for settings.
        """
        super().__init__(config)

    @override
    def _get_content_context(self, metadata: PdfMetadata) -> str:
        """Get content context string for AI prompts.

        Parameters
        ----------
        metadata : PdfMetadata
            PDF metadata.

        Returns
        -------
        str
            Context string for AI prompts.
        """
        return (
            f"PDF document '{metadata.title or 'Untitled'}' "
            f"({metadata.pages} pages, {metadata.source_type} source)"
        )

    @override
    def _get_filename_context(self, metadata: PdfMetadata) -> tuple[str, str]:
        """Get title and source context for filename generation.

        Parameters
        ----------
        metadata : PdfMetadata
            PDF metadata.

        Returns
        -------
        tuple[str, str]
            Tuple of (title, source_identifier) for filename generation.
        """
        source_identifier = metadata.source_type
        if metadata.source_type == 'arxiv':
            source_identifier = "arXiv"
        elif metadata.source_type == 'url':
            # Extract domain from URL
            try:
                parsed_url = urlparse(metadata.url)
                domain = parsed_url.netloc.lower()
                if domain.startswith("www."):
                    domain = domain[4:]
                source_identifier = domain
            except Exception:
                source_identifier = "PDF"
        else:
            source_identifier = "PDF"

        return metadata.title or "Untitled", source_identifier

    def extract_pdf_metadata(self, content: ConvertedContent) -> PdfMetadata:
        """Extract metadata from converted PDF content.

        Parameters
        ----------
        content : ConvertedContent
            Converted PDF content object.

        Returns
        -------
        PdfMetadata
            Extracted PDF metadata structure.

        Examples
        --------
        >>> generator = PdfMetadataGenerator()
        >>> content = ConvertedContent(...)
        >>> metadata = generator.extract_pdf_metadata(content)
        >>> metadata.source_type
        "arxiv"
        """
        try:
            logger.info(f"Extracting metadata from PDF: {content.url}")

            # Try AI-powered extraction first
            ai_metadata = None
            if self._openai_client:
                try:
                    ai_metadata = self._extract_metadata_with_ai(content.markdown)
                    logger.info("Successfully extracted metadata using AI")
                except Exception as e:
                    logger.warning(f"AI metadata extraction failed: {e}")

            # Use AI results if available, otherwise fall back to regex
            if ai_metadata:
                title = ai_metadata.get('title')
                description = ai_metadata.get('description')
                author = ai_metadata.get('author')
                publish_date = ai_metadata.get('publish_date')
                content_type = ai_metadata.get('content_type', 'document')
                ai_language = ai_metadata.get('language')
            else:
                logger.info("Falling back to regex-based metadata extraction")
                title = self._extract_title_from_content(content.markdown)
                description = self._extract_description_from_content(content.markdown)
                author = self._extract_author_from_content(content.markdown)
                publish_date = self._extract_publish_date_from_content(content.markdown)
                content_type = self._determine_pdf_content_type(content.url, content.markdown)
                ai_language = None

            # Get conversion metadata
            pages = content.metadata.get('pages', 0)
            language = ai_language or content.metadata.get('language', 'unknown')

            metadata = PdfMetadata(
                url=content.url,
                title=title,
                description=description,
                author=author,
                publish_date=publish_date,
                conversion_date=content.conversion_date,
                content_type=content_type,
                word_count=content.word_count,
                source_type=content.source_type,
                pages=pages,
                language=language,
            )

            logger.info(f"Extracted metadata: title='{title}', type='{content_type}', pages={pages}")
            return metadata

        except Exception as e:
            error_msg = f"Failed to extract metadata from PDF {content.url}: {e}"
            logger.error(error_msg)
            raise MetadataGenerationError(error_msg) from e

    def _extract_metadata_with_ai(self, content: str) -> dict[str, Any]:
        """Extract comprehensive metadata using a single OpenAI call.

        Parameters
        ----------
        content : str
            Markdown content from PDF.

        Returns
        -------
        dict[str, Any]
            Dictionary containing extracted metadata fields.

        Raises
        ------
        OpenAIError
            If AI extraction fails.
        """
        if not self._openai_client:
            from common.ai_metadata import OpenAIError
            raise OpenAIError("OpenAI client not initialized")

        # Truncate content to avoid token limits while preserving key sections
        max_content_length = 4000
        if len(content) > max_content_length:
            # Take first part and last part to capture title/abstract and conclusions
            first_part = content[:max_content_length // 2]
            last_part = content[-(max_content_length // 2):]
            truncated_content = first_part + "\n\n... [content truncated] ...\n\n" + last_part
        else:
            truncated_content = content

        prompt = f"""
Analyze the following PDF content and extract metadata in JSON format.
Return ONLY valid JSON with no additional text or formatting.

Content:
{truncated_content}

Extract the following information:
{{
  "title": "Document title (required - if no clear title, create a descriptive one based on content)",
  "description": "Brief description or abstract (2-3 sentences max, null if none found)",
  "author": "Author name(s) as single string (null if none found)",
  "publish_date": "Publication date in YYYY-MM-DD format (null if none found)",
  "content_type": "One of: research_paper, manual, report, book, presentation, document",
  "language": "Document language code (en, es, fr, etc., null if unknown)"
}}

Guidelines:
- For title: Extract the main document title. If unclear, create a descriptive title based on the content
- For description: Look for abstract, summary, or introduction. Keep it concise
- For author: Extract author names in format "FirstName LastName" or "LastName, FirstName"
- For publish_date: Look for publication, submission, or creation dates
- For content_type: Classify based on structure and content indicators
- For language: Detect the primary language of the document
"""

        try:
            response = self._openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a metadata extraction assistant. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=300
            )

            content_result = response.choices[0].message.content
            if not content_result:
                from common.ai_metadata import OpenAIError
                raise OpenAIError("OpenAI returned empty content")

            # Parse JSON response
            import json
            try:
                metadata_dict = json.loads(content_result.strip())
                logger.info(f"AI extracted metadata: {metadata_dict}")
                return metadata_dict
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {content_result}")
                from common.ai_metadata import OpenAIError
                raise OpenAIError(f"Invalid JSON response from AI: {e}")

        except Exception as e:
            error_msg = f"AI metadata extraction failed: {e}"
            logger.error(error_msg)
            from common.ai_metadata import OpenAIError
            raise OpenAIError(error_msg) from e

    def _extract_title_from_content(self, content: str) -> str | None:
        """Extract title from PDF content.

        Parameters
        ----------
        content : str
            Markdown content from PDF.

        Returns
        -------
        str or None
            Extracted title or None if not found.
        """
        if not content:
            return None

        # Look for first H1 heading
        h1_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
        if h1_match:
            title = h1_match.group(1).strip()
            # Clean up common title artifacts
            title = re.sub(r'\s+', ' ', title)
            return title

        # Look for title patterns in first few lines
        lines = content.split('\n')[:10]
        for line in lines:
            line = line.strip()
            if (len(line) > 10 and
                not line.startswith('#') and
                not line.startswith('*') and
                not line.startswith('-') and
                not line.lower().startswith('abstract')):
                # Check if line looks like a title (reasonable length, no lowercase start)
                if len(line) < 200 and line[0].isupper():
                    return line

        return None

    def _extract_description_from_content(self, content: str) -> str | None:
        """Extract description/abstract from PDF content.

        Parameters
        ----------
        content : str
            Markdown content from PDF.

        Returns
        -------
        str or None
            Extracted description or None if not found.
        """
        if not content:
            return None

        # Look for abstract section
        abstract_patterns = [
            r"(?i)^#+\s*abstract\s*\n(.*?)(?=^#+|\n\n\n|$)",
            r"(?i)abstract[:.\s]*(.*?)(?=\n\n\n|introduction|keywords|$)",
            r"(?i)^abstract\s*\n(.*?)(?=\n\n\n|^[A-Z]|$)",
        ]

        for pattern in abstract_patterns:
            match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
            if match:
                abstract = match.group(1).strip()
                # Clean up and limit length
                abstract = re.sub(r'\s+', ' ', abstract)
                if len(abstract) > 500:
                    abstract = abstract[:500] + "..."
                return abstract

        return None

    def _extract_author_from_content(self, content: str) -> str | None:
        """Extract author from PDF content.

        Parameters
        ----------
        content : str
            Markdown content from PDF.

        Returns
        -------
        str or None
            Extracted author or None if not found.
        """
        if not content:
            return None

        # Look for author patterns in first part of document
        lines = content.split('\n')[:20]

        # Common author patterns
        for line in lines:
            line = line.strip()

            # Look for explicit author mentions
            if re.search(r'(?i)(authors?|by)\s*[:.]', line):
                # Extract text after "Author:" or "By:"
                match = re.search(r'(?i)(?:authors?|by)\s*[:.]?\s*(.+)', line)
                if match:
                    author = match.group(1).strip()
                    # Clean up common artifacts
                    author = re.sub(r'\s+', ' ', author)
                    if len(author) < 100:  # Reasonable author length
                        return author

            # Look for lines that might be author names (after title, before abstract)
            if (len(line) > 5 and len(line) < 100 and
                not line.startswith('#') and
                not line.lower().startswith('abstract') and
                re.search(r'[A-Z][a-z]+ [A-Z]', line)):  # Has capitalized words
                return line

        return None

    def _extract_publish_date_from_content(self, content: str) -> str | None:
        """Extract publication date from PDF content.

        Parameters
        ----------
        content : str
            Markdown content from PDF.

        Returns
        -------
        str or None
            Extracted date in YYYY-MM-DD format or None if not found.
        """
        if not content:
            return None

        # Look for date patterns in first part of document
        first_part = content[:2000]

        # Common date patterns
        date_patterns = [
            r'(?i)(?:published|date|submitted)[:.]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            r'(?i)(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            r'(?i)((?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2},?\s+\d{4})',
            r'(?i)(\d{1,2}\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4})',
        ]

        for pattern in date_patterns:
            match = re.search(pattern, first_part)
            if match:
                date_str = match.group(1)
                # Try to normalize to YYYY-MM-DD format
                try:
                    from datetime import datetime

                    # Handle different formats
                    for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%B %d, %Y', '%B %d %Y', '%d %B %Y']:
                        try:
                            parsed_date = datetime.strptime(date_str, fmt)
                            return parsed_date.strftime('%Y-%m-%d')
                        except ValueError:
                            continue
                except ImportError:
                    pass

                # Fallback: if it looks like YYYY-MM-DD or YYYY/MM/DD, use as is
                if re.match(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', date_str):
                    return date_str.replace('/', '-')

        return None

    def _determine_pdf_content_type(self, url: str, content: str) -> str:
        """Determine content type based on URL and content.

        Parameters
        ----------
        url : str
            URL or path of the PDF.
        content : str
            Content text for analysis.

        Returns
        -------
        str
            Content type classification.
        """
        url_lower = url.lower()

        # Check source type first
        if 'arxiv.org' in url_lower:
            return 'research_paper'

        # Check content patterns
        if content:
            content_lower = content.lower()

            # Research paper indicators
            if any(indicator in content_lower for indicator in [
                'abstract', 'introduction', 'methodology', 'results', 'conclusion',
                'references', 'bibliography', 'doi:', 'arxiv:', 'ieee', 'acm'
            ]):
                return 'research_paper'

            # Manual/documentation indicators
            elif any(indicator in content_lower for indicator in [
                'manual', 'documentation', 'guide', 'instructions', 'tutorial',
                'version', 'chapter', 'table of contents'
            ]):
                return 'manual'

            # Report indicators
            elif any(indicator in content_lower for indicator in [
                'report', 'analysis', 'findings', 'summary', 'executive summary'
            ]):
                return 'report'

            # Book indicators
            elif any(indicator in content_lower for indicator in [
                'chapter', 'preface', 'foreword', 'copyright', 'isbn'
            ]):
                return 'book'

        return 'document'  # Default fallback

    def generate_ai_content_for_pdf(
        self, metadata: PdfMetadata, content_preview: str
    ) -> AIGeneratedContent:
        """Generate AI-powered filename, tags, and authors for PDF content.

        Parameters
        ----------
        metadata : PdfMetadata
            PDF metadata to analyze.
        content_preview : str
            First portion of content for AI analysis.

        Returns
        -------
        AIGeneratedContent
            AI-generated filename, tags, and authors.

        Examples
        --------
        >>> generator = PdfMetadataGenerator()
        >>> metadata = PdfMetadata(...)
        >>> ai_content = generator.generate_ai_content_for_pdf(metadata, preview)
        >>> ai_content.filename
        "Attention-Is-All-You-Need-arXiv"
        """
        # Use the base class method
        return super().generate_ai_content(metadata, content_preview)

    def construct_frontmatter(
        self,
        metadata: PdfMetadata,
        ai_content: AIGeneratedContent | None = None
    ) -> str:
        """Construct YAML frontmatter for PDF content Obsidian note.

        Parameters
        ----------
        metadata : PdfMetadata
            PDF metadata.
        ai_content : AIGeneratedContent, optional
            AI-generated content. If None, only basic metadata is included.

        Returns
        -------
        str
            YAML frontmatter string.

        Examples
        --------
        >>> generator = PdfMetadataGenerator()
        >>> frontmatter = generator.construct_frontmatter(metadata, ai_content)
        >>> "title:" in frontmatter
        True
        """
        # Extra fields specific to PDF content
        extra_fields = {
            "source": "pdf",
            "url": metadata.url,
            "source_type": metadata.source_type,
            "conversion_date": metadata.conversion_date.split("T")[0],
            "word_count": metadata.word_count,
            "content_type": metadata.content_type,
            "pages": metadata.pages,
            "language": metadata.language,
        }

        if metadata.publish_date:
            extra_fields["publish_date"] = metadata.publish_date

        return super()._construct_frontmatter_base(metadata, ai_content, extra_fields)

    def generate_markdown_content(
        self,
        metadata: PdfMetadata,
        content: str,
        ai_content: AIGeneratedContent | None = None,
    ) -> str:
        """Generate complete markdown content with frontmatter.

        Parameters
        ----------
        metadata : PdfMetadata
            PDF metadata.
        content : str
            Converted PDF content.
        ai_content : AIGeneratedContent, optional
            AI-generated content for enhanced metadata.

        Returns
        -------
        str
            Complete markdown content with frontmatter.

        Examples
        --------
        >>> generator = PdfMetadataGenerator()
        >>> markdown = generator.generate_markdown_content(metadata, content, ai_content)
        >>> markdown.startswith("---")
        True
        """
        frontmatter = self.construct_frontmatter(metadata, ai_content)
        return f"{frontmatter}\n\n{content}"

    def get_suggested_filename(
        self,
        metadata: PdfMetadata,
        ai_content: AIGeneratedContent | None = None
    ) -> str:
        """Get suggested filename for the markdown file.

        Parameters
        ----------
        metadata : PdfMetadata
            PDF metadata.
        ai_content : AIGeneratedContent, optional
            AI-generated content with filename suggestion.

        Returns
        -------
        str
            Suggested filename with .md extension.

        Examples
        --------
        >>> generator = PdfMetadataGenerator()
        >>> filename = generator.get_suggested_filename(metadata, ai_content)
        >>> filename.endswith(".md")
        True
        """
        return super()._get_suggested_filename_base(metadata, ai_content)
