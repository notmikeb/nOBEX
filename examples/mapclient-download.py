#!/usr/bin/env python

import bluetooth, os, struct, sys
from xml.etree import ElementTree
from xml.dom import minidom
from PyOBEX import client, headers, responses

def dump_xml(element, file_name):
    fd = open(file_name, 'w')
    fd.write('<?xml version="1.0"?>\n<!DOCTYPE vcard-listing SYSTEM "vcard-listing.dtd">\n')
    rough_string = ElementTree.tostring(element, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    pretty_string = reparsed.toprettyxml()
    fd.write(pretty_string[23:]) # skip xml declaration
    fd.close()

def escape_ampersands(s):
    # Terrible hack to work around Python getting mad at things like
    # <foo goo="Moo & Roo" />
    us = str(s, encoding='utf-8')
    us2 = '&amp;'.join(us.split('&'))
    return bytes(us2, encoding='utf-8')

def connect(device_address):
    d = bluetooth.find_service(address=device_address, uuid="1134")
    if not d:
        sys.stderr.write("No message access service found.\n")
        sys.exit(1)

    port = d[0]["port"]

    # Use the generic Client class to connect to the phone.
    c = client.Client(device_address, port)
    result = c.connect()

    if not isinstance(result, responses.ConnectSuccess):
        sys.stderr.write("Failed to connect to phone.\n")
        sys.exit(1)

    return c

def get_file(c, src_path, dest_path, verbose=True, folder_name=None):
    if verbose:
        if folder_name is not None:
            print("Fetching %s/%s" % (folder_name, src_path))
        else:
            print("Fetching %s" % src_path)

    hdrs, card = c.get(src_path, header_list=[headers.Type(b'x-bt/message')])
    with open(dest_path, 'wb') as f:
        f.write(card)

def dump_dir(c, src_path, dest_path):
    src_path = src_path.strip("/")

    # since some people may still be holding back progress with Python 2, I'll support
    # them for now and not use the Python 3 exists_ok option :(
    try:
        os.makedirs(dest_path)
    except OSError as e:
        pass

    # Access the list of vcards in the directory
    hdrs, cards = c.get(src_path, header_list=[headers.Type(b'x-bt/MAP-msg-listing')])
    print(cards) #debug

    # Parse the XML response to the previous request.
    # Extract a list of file names in the directory
    names = []
    try:
        root = ElementTree.fromstring(cards)
    except ElementTree.ParseError:
        root = ElementTree.fromstring(escape_ampersands(cards))
    dump_xml(root, "/".join([dest_path, "mlisting.xml"]))
    for card in root.findall("msg"):
        names.append(card.attrib["handle"])

    c.setpath(src_path)

    # get all the files
    for name in names:
        get_file(c, name, "/".join([dest_path, name]), folder_name=src_path)

    # return to the root directory
    depth = len([f for f in src_path.split("/") if len(f)])
    for i in range(depth):
        c.setpath(to_parent=True)

def main():
    if len(sys.argv) != 3:
        sys.stderr.write("Usage: %s <device address> <dest directory>\n" % sys.argv[0])
        return 1

    device_address = sys.argv[1]
    dest_dir = os.path.abspath(sys.argv[2]) + "/"

    c = connect(device_address)

    # dump every folder
    dump_dir(c, "telecom/msg/deleted", dest_dir + "telecom/msg/deleted")
    dump_dir(c, "telecom/msg/draft",   dest_dir + "telecom/msg/draft")
    dump_dir(c, "telecom/msg/inbox",   dest_dir + "telecom/msg/inbox")
    dump_dir(c, "telecom/msg/outbox",  dest_dir + "telecom/msg/outbox")
    dump_dir(c, "telecom/msg/sent",    dest_dir + "telecom/msg/sent")

    c.disconnect()
    return 0

if __name__ == "__main__":
    sys.exit(main())