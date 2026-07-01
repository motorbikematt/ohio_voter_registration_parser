import re
from bs4 import BeautifulSoup, NavigableString

def htmlbook_to_markdown(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    markdown_lines = []

    # Parse main elements inside the book body
    book_body = soup.find('body', {'data-type': 'book'})
    target_root = book_body if book_body else soup

    def process_element(element, indent_level=0):
        if isinstance(element, NavigableString):
            text = str(element).strip()
            if text:
                return text
            return ""

        tag_name = element.name

        # Structural blocks matching textbook sections/parts
        if tag_name in ['section', 'div', 'nav']:
            data_type = element.get('data-type', '')
            class_list = element.get('class', [])
            
            # Process children blocks recursively
            inner_content = ""
            for child in element.children:
                inner_content += process_element(child, indent_level)
            
            # Formatting custom text boxes (e.g., Foundational Facts)
            if 'textbox' in class_list:
                boxed = "\n\n> ### 📦 BOXOUT\n"
                for line in inner_content.strip().split('\n'):
                    boxed += f"> {line}\n"
                return boxed + "\n"
                
            return "\n" + inner_content + "\n"

        # Headers
        if tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(tag_name[1])
            text = element.get_text().strip()
            return f"\n\n{'#' * level} {text}\n"

        # Paragraphs
        if tag_name == 'p':
            text_pieces = []
            for child in element.children:
                text_pieces.append(process_element(child, indent_level))
            p_text = "".join(text_pieces).strip()
            # Handle clean separation for strong text headers inside pseudo-paragraphs
            p_text = re.sub(r'^#(.*)', r'\1', p_text) 
            return f"\n\n{p_text}"

        # Inline Text Formatting
        if tag_name == 'strong' or tag_name == 'b':
            return f"**{element.get_text().strip()}**"
        if tag_name == 'em' or tag_name == 'i':
            return f"*{element.get_text().strip()}*"
        
        # Lists
        if tag_name in ['ul', 'ol']:
            list_content = ""
            for child in element.find_all('li', recursive=False):
                prefix = "1." if tag_name == 'ol' else "*"
                li_text = "".join([process_element(c, indent_level + 2) for c in child.children]).strip()
                list_content += f"\n{' ' * indent_level}{prefix} {li_text}"
            return "\n" + list_content + "\n"

        # Links
        if tag_name == 'a':
            href = element.get('href', '')
            text = element.get_text().strip()
            if text and href:
                return f"[{text}]({href})"
            return text

        # Images
        if tag_name == 'img':
            src = element.get('src', '')
            alt = element.get('alt', 'Image')
            return f"\n\n![{alt}]({src})"

        # Tables
        if tag_name == 'table':
            table_md = "\n\n"
            rows = element.find_all('tr')
            for i, row in enumerate(rows):
                cols = [t.get_text().strip().replace('\n', ' ') for t in row.find_all(['td', 'th'])]
                table_md += "| " + " | ".join(cols) + " |\n"
                if i == 0: # Insert markdown table separator alignment
                    table_md += "| " + " | ".join(['---'] * len(cols)) + " |\n"
            return table_md + "\n"

        # Fallback loop execution for unhandled generic tags
        output = ""
        for child in element.children:
            output += process_element(child, indent_level)
        return output

    # Run the processor starting from the body root
    raw_md = process_element(target_root)
    
    # Post-process cleanup of structural white space irregularities
    cleaned_md = re.sub(r'\n{3,}', '\n\n', raw_md)
    cleaned_md = re.sub(r' +', ' ', cleaned_md)
    return cleaned_md.strip()

if __name__ == "__main__":
    import sys
    
    # Implementation instructions for local terminal execution
    if len(sys.argv) < 3:
        print("Usage: python convert.py input.html output.md")
        sys.exit(1)
        
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    
    print(f"Reading structural layout from: {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        html_data = f.read()
        
    print("Executing extraction pipeline...")
    markdown_output = htmlbook_to_markdown(html_data)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(markdown_output)
        
    print(f"Verbatim Markdown structural copy written to: {output_path}")