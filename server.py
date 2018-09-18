"""
COSC264 Assignment
Author: sjs227
Due date: 21/08/2018 

Server application that handles DT-Requests in English, Maori and German, where the server will respond
with the current date and time with a text representation of the date or time depending on what request 
type was sent to the server. Some basic error checking is done when running the program and when receiving
packets
"""


from select import select
from datetime import datetime
import argparse
import socket
import sys

# Packet header constants
MAGIC_NUMBER = 0x497E
DT_REQ = 0x0001
DT_RES = 0x0002
REQ_DATE = 0x0001
REQ_TIME = 0x0002
TIMEOUT = 1.0


# Constants for textual representation of the date and time for each language
STRINGS = {0x1: ["Today's date is {0} {1}, {2}", "The current time is {0:02d}:{1:02d}"],
           0x2: ["Ko te ra o tenei ra ko {0} {1}, {2}", "Ko te wa o tenei wa {0:02d}:{1:02d}"],
           0x3: ["Heute ist der {1}. {0} {2}", "Die Uhrzeit ist {0:02d}:{1:02d}"]}

MONTHS = {0x1: ["January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"],
          0x2: ["Kohitātea", "Hui-tanguru", "Poutū-te-rangi", "Paenga-whāwhā", "Haratua", "Pipiri",
                "Hōngongoi", "Here-turi-kōkā", "Mahuru", "Whiringa-ā-nuku", "Whiringa-ā-rangi", "Hakihea"],
          0x3: ["Januar", "Februar", "März", "April", "Mai", "Juni",
                "Juli", "August", "September", "Oktober", "November", "Dezember"]}


def check_arguments():
    """
    Checks the arguments supplied to the program upon execution using argparser. Also checks that the port
    numbers are valid before returning the port numbers to main.

    :return: Int for english, maori and german ports to be opened
    """

    # Defining the command line positional arguments and types
    parser = argparse.ArgumentParser()
    parser.add_argument('EN_Port', help="Port number for English DT Requests", type=int)
    parser.add_argument('MI_Port', help="Port number for Maori DT Requests", type=int)
    parser.add_argument('GE_Port', help="Port number for German DT Requests", type=int)
    args = parser.parse_args()

    # Checks each of the ports are in the correct range, exiting otherwise
    if args.EN_Port not in range(1024, 64001):
        print("[ERROR] ** EN_Port not in range [1024 - 64000]\nStopping..\n")
        sys.exit()

    if args.MI_Port not in range(1024, 64001):
        print("[ERROR] ** MI_Port not in range [1024 - 64000]\nStopping..\n")
        sys.exit()

    if args.GE_Port not in range(1024, 64001):
        print("[ERROR] ** GE_Port not in range [1024 - 64000]\nStopping..\n")
        sys.exit()

    return args.EN_Port, args.MI_Port, args.GE_Port


def process_packet(packet, addr):
    """
    Processes a received packet by checking the length of the packet, magic number and request type.
    If request is not valid the packet is dropped

    :param packet: Bytearray of the packet received by the server
    :param addr: Address tuple of the sender of the packet
    :return: None if packet is not a valid DT-Request, request type if the packet is a
            valid DT-Request
    """

    # Checking packet length
    if len(packet) != 6:
        err_str = "[ALERT] ** Unrecognised packet received:\n\tSource: {0}:{1}\n\tData: {2}"
        print(err_str.format(addr[0], addr[1], packet))
        return None

    # Checking magic number
    if int.from_bytes(packet[0:2], "big") != MAGIC_NUMBER:
        err_str = "[ALERT] ** Unrecognised packet received:\n\tSource: {0}:{1}\n\tData: {2}"
        print(err_str.format(addr[0], addr[1], packet))
        return None

    # Checking if the packet is a DT Request 
    if int.from_bytes(packet[2:4], "big") != DT_REQ:
        err_str = "[ALERT] ** Non DT Request received:\n\tSource: {0}:{1}\n\tData: {2}"
        print(err_str.format(addr[0], addr[1], packet))
        return None

    # If packet passes all checks, return the type of request (date or time) as int
    return int.from_bytes(packet[5:6], "big")


def create_packet(request_type, lang_code):
    """
    Creates a DT-Response packet that contains a 13 byte header and a text field containing a textual
    representation of the given request type. The header contains: Magic number, packet type, language code
    and yyyy, mm, dd, hh, mm in each of their own fields. Finally a length of the text field.

    :param request_type: Request code for either date or time
    :param lang_code: Language of the response to be used
    :return: A bytearray of the packet to return to the DT-Request sender
    """

    curr_time = datetime.now()

    # Getting each of the date and time attributes from the datetime object
    minute = curr_time.minute
    hour = curr_time.hour
    day = curr_time.day
    month = curr_time.month
    year = curr_time.year

    # Forms the textual representation for the different request types
    text_string = ""
    if request_type == REQ_DATE:
        text_string = STRINGS[lang_code][0].format(MONTHS[lang_code][month - 1], day, year)
    if request_type == REQ_TIME:
        text_string = STRINGS[lang_code][1].format(hour, minute)

    # Creating a bytearray of 13 header bytes and length of the text string
    length = len(text_string.encode('UTF-8'))
    packet = bytearray(13 + length)

    # Inserting each of the values into the header and encoding the text string as UTF-8
    packet[0:2] = MAGIC_NUMBER.to_bytes(2, "big")
    packet[2:4] = DT_RES.to_bytes(2, "big")
    packet[4:6] = lang_code.to_bytes(2, "big")
    packet[6:8] = year.to_bytes(2, "big")
    packet[8:12] = [month, day, hour, minute]
    packet[12] = length
    
    # Neat python feature, unused bytes at the end of the bytearray are deleted from memory when 
    # a slice is allocated as follows:
    packet[13:] = text_string.encode('UTF-8')

    return packet


def socket_setup(eng_port, mao_port, ger_port):
    """
    Opens 3 sockets on the unique given ports for each language, then enters an infinite (CPU blocking)
    loop to listen for requests. When a request is received it is processed and a response is sent if
    it is a valid DT-Request

    :param eng_port: Port to be used for the English response
    :param mao_port: Port to be used for the Maori response
    :param ger_port: Port to be used for the German response
    """

    # Opening a socket on each of the given ports
    try:
        en_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        en_sock.bind(('', eng_port))
        mi_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        mi_sock.bind(('', mao_port))
        ge_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ge_sock.bind(('', ger_port))
    except socket.error as e:
        print(e)
        print("Stopping..\n")
        sys.exit()

    # Converting the port numbers into language codes
    languages = {eng_port: 0x1, mao_port: 0x2, ger_port: 0x3}

    # Infinite listen loop using a select() call to block execution until packet is received
    # Loop can only be exited when the server encounters an error
    while True:
        readable, writable, exceptional = select([en_sock, mi_sock, ge_sock], [], [], TIMEOUT)

        # If there is data in the readable buffer then packet processing may occur
        if len(readable) > 0:
            sock = readable[0]
            received_packet, addr = sock.recvfrom(1024)
            request = process_packet(received_packet, addr)

            # Checking if the request is valid, if process_packet() returns none then the packet is dropped
            # If not then a response packet is generated and sent
            if request:
                ack_str = "[INFO] -- Received DT Request from {0}:{1}\n\tType code: {2}\n\tLang code: {3}"
                print(ack_str.format(addr[0], addr[1], request, languages[readable[0].getsockname()[1]]))
                to_send = create_packet(request, languages[readable[0].getsockname()[1]])
                sock.sendto(to_send, addr)
                print("[INFO] -- Sent DT Response to {0}:{1}\n".format(addr[0], addr[1]))


def main():
    """
    Program entry, gets ports from check_arguments() and calls socket_setup to handle connections to the
    given ports
    """
    eng_port, mao_port, ger_port = check_arguments()
    socket_setup(eng_port, mao_port, ger_port)


if __name__ == "__main__":
    main()
