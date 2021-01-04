from collections import namedtuple
from struct import pack_into

from .constants import CLASS_MASK, CLASS_UNIQUE, FLAGS_QR_QUERY
from .util import byte_count_of_lists, check_name, fill_buffer, pack_string, string_packed_len


class DNSEntry:
    def __init__(self, name: str, type_: int, class_: int) -> None:
        self.key = name.lower()
        self.name = name
        self.type = type_
        self.class_ = class_ & CLASS_MASK
        self.unique = (class_ & CLASS_UNIQUE) != 0


class DNSQuestion(namedtuple("DNSQuestion", ["query", "type", "query_class"])):
    @property
    def checked_query(self) -> "List[bytes]":
        return check_name(self.query)

    def to_bytes(self) -> bytes:
        checked_query = self.checked_query
        query_len = string_packed_len(checked_query)
        buffer = bytearray(query_len + 4)
        pack_string(buffer, self.checked_query)
        pack_into("!HH", buffer, query_len, self.type, self.query_class)
        return buffer


class DNSQuestionWrapper(namedtuple("DNSQuestionWrapper", ["questions"])):
    questions: "List[DNSQuestion]"

    def to_bytes(self) -> bytes:
        question_bytes = [question.to_bytes() for question in self.questions]
        buffer = bytearray(sum(len(qb) for qb in question_bytes) + 12)
        buffer[:12] = FLAGS_QR_QUERY.to_bytes(12, "big")
        buffer[4:6] = len(self.questions).to_bytes(2, "big")
        index = 12
        for question_bytes_item in question_bytes:
            end = index + len(question_bytes_item)
            buffer[index:end] = question_bytes_item
            index = end
        return buffer


class DNSRecord(namedtuple("DNSRecord", ["name", "record_type", "query_class", "time_to_live", "rdata"])):
    name: str
    record_type: int
    query_class: int
    time_to_live: int
    rdata: bytes

    @property
    def checked_name(self) -> "List[bytes]":
        return check_name(self.name)

    def to_bytes(self) -> bytes:
        checked_name = self.checked_name
        query_len = string_packed_len(checked_name)
        header_length = query_len + 8
        rdata_length = len(self.rdata)
        payload_length = 2 + rdata_length
        buffer = bytearray(header_length + payload_length)
        pack_string(buffer, checked_name)
        index = query_len
        pack_into("!HHLH", buffer, index, self.record_type, self.query_class, self.time_to_live, rdata_length)
        index += 10
        end_index = index + rdata_length
        buffer[index:end_index] = self.rdata
        return buffer


class DNSResponse(
    namedtuple("DNSResponse", ["transaction_id", "message_type", "questions", "answers", "authorities", "additional"])
):
    transaction_id: int
    message_type: int
    questions: "List[DNSQuestion]"
    answers: "List[DNSRecord]"
    authorities: "List[DNSRecord]"
    additional: "List[DNSRecord]"

    def to_bytes(self) -> bytes:
        question_bytes = [question.to_bytes() for question in self.questions]
        answer_bytes = [answer.to_bytes() for answer in self.answers]
        authorities_bytes = [authority.to_bytes() for authority in self.authorities]
        additional_bytes = [additional.to_bytes() for additional in self.additional]
        payload_length = byte_count_of_lists(question_bytes, answer_bytes, authorities_bytes, additional_bytes)
        buffer = bytearray(12 + payload_length)
        pack_into(
            "!HHHHHH",
            buffer,
            0,
            self.transaction_id,
            self.message_type,
            len(question_bytes),
            len(answer_bytes),
            len(authorities_bytes),
            len(additional_bytes),
        )
        index = 12
        for question_byte_list in question_bytes:
            index = fill_buffer(buffer, question_byte_list, index)
        for answer_byte_list in answer_bytes:
            index = fill_buffer(buffer, answer_byte_list, index)
        for authority_byte_list in authorities_bytes:
            index = fill_buffer(buffer, authority_byte_list, index)
        for additional_byte_list in additional_bytes:
            index = fill_buffer(buffer, additional_byte_list, index)
        return buffer
