import xml.etree.ElementTree as elementTree
import sys

if __name__ == '__main__':
    args_count = len(sys.argv)
    if args_count <= 1:
        raise Exception("Invalid xml file path")

    xml_path = sys.argv[1]

    if not xml_path.endswith(".xml"):
        raise Exception("Invalid file type (only .xml supported)")

    search_filter = sys.argv[2] if args_count >= 3 else None

    tree = elementTree.parse(xml_path)
    root = tree.getroot()

    result = root.findall(".//*Value")
    if len(result) == 0:
        print("No matching")
    else:
        output_file = open(search_filter.lower() + ".sql", "w")

        for value in result:
            text = value.text
            if search_filter is None or search_filter.lower() in text.lower():
                print(value.text)
                output_file.write(value.text + "\n")

        output_file.close()