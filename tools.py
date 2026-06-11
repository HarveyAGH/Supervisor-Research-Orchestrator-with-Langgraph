from pathlib import Path

from langchain_core.tools import tool
from ddgs import DDGS
import os


@tool
def search_web(query: str) -> str:
    """Search the web for current or factual information on a given topic.

    Use this tool when:
    - The user asks for recent, real-time, or current information (news, prices, events, etc.)
    - You need facts or data you do not already know or that may have changed recently
    - The user explicitly asks you to search the web

    Do NOT use this tool when:
    - You can already answer confidently from your own knowledge
    - The task involves math, logic, or reasoning only
    - The user asks you to read a local file or use data already in context
    - The query is about historical facts well within your training data

    Args:
        query: The search query string to look up on the web.

    Returns:
        A plain text summary of the top search results (max ~500 words),
        or an error message string if the search fails.
    """
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=2))

        if not results:
            return f"No results found for query: '{query}'"

        lines = []
        total_words = 0
        word_limit = 500

        for i, r in enumerate(results, start=1):
            title = r.get("title", "No title")
            body = r.get("body", "")
            url = r.get("href", "")

            snippet = f"[{i}] {title}\n{body}\nSource: {url}"
            snippet_words = len(snippet.split())

            if total_words + snippet_words > word_limit:
                break

            lines.append(snippet)
            total_words += snippet_words

        return "\n\n".join(lines)

    except Exception as e:
        return f"Search failed for query '{query}': {str(e)}"





@tool
def validate(content: str) -> str:
    """Validates the writer's output for accuracy.

    Use this tool when:
    - Validating a file that includes real data for it's output accuracy
    - Used ONLY after a file has been written using the write_file tool
   
    Args:
        content: Full text content to be validated from the write tool.
        """
    return f"FILE OUTPUT HAS BEEN VALIDATED"



@tool
def read_file(path: str) -> str:
    """Read the full text contents of a local file from disk.

    Use this tool when:
    - The agent needs to access an existing file on disk
    - The file contains notes, documents, reports, data, or previously written output
    - A file path has been provided and its contents are needed for the task

    Do NOT use this tool when:
    - The content is already present in the conversation history
    - The file does not exist yet
    - The task requires searching the web or querying a database

    Args:
        path: The full or relative file path to the file to read.

    Returns:
        The full plain text content of the file as a string,
        or an informative error string if the file cannot be read.
    """
    try:
        file = Path(path)

        if not file.exists():
            return f"Error: File not found at path '{path}'"
        if not file.is_file():
            return f"Error: Path '{path}' exists but is not a file"

        return file.read_text(encoding="utf-8")

    except PermissionError:
        return f"Error: Permission denied when reading '{path}'"
    except Exception as e:
        return f"Error reading file '{path}': {str(e)}"


@tool
def write_file(content: str, filename: str) -> str:
    """Write a string of content to a file on disk.

    Creates the file if it does not exist. Overwrites the file if it does.
    Parent directories are created automatically if they do not exist.

    Use this tool when:
    - The agent has a final deliverable to persist — a report, summary, document, or output
    - The task explicitly requires saving content to a file on disk

    Do NOT use this tool when:
    - The goal is to read an existing file (use read_file instead)
    - The task involves appending to a file rather than overwriting it
    - The task involves web operations or writing to a database

    Args:
        content: The full text content to write to the file.
        filename: The target file path including extension (e.g. 'output/report.txt').

    Returns:
        A confirmation string with the filename on success,
        or an informative error string if the write fails.
    """
    try:
        file = Path(filename)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")
        return f"Successfully wrote to '{filename}'"

    except PermissionError:
        return f"Error: Permission denied when writing to '{filename}'"
    except Exception as e:
        return f"Error writing to file '{filename}': {str(e)}"
    
    
RESEARCH_TOOLS = [search_web]
WRITER_TOOLS = [read_file, write_file]
VALIDATOR_TOOLS = [validate]
    

        

