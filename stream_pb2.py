# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: stream.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='stream.proto',
  package='protos',
  syntax='proto3',
  serialized_options=b'Z dangerous.tech/streamdl;streamdl',
  create_key=_descriptor._internal_create_key,
  serialized_pb=b'\n\x0cstream.proto\x12\x06protos\"R\n\nStreamInfo\x12\x0c\n\x04site\x18\x01 \x01(\t\x12\x0c\n\x04user\x18\x02 \x01(\t\x12\x0f\n\x07quality\x18\x03 \x01(\t\x12\x17\n\x0foutput_template\x18\x04 \x01(\t\",\n\x0eStreamResponse\x12\x0b\n\x03url\x18\x01 \x01(\t\x12\r\n\x05\x65rror\x18\x02 \x01(\x05\x32\x41\n\x06Stream\x12\x37\n\tGetStream\x12\x12.protos.StreamInfo\x1a\x16.protos.StreamResponseB\"Z dangerous.tech/streamdl;streamdlb\x06proto3'
)




_STREAMINFO = _descriptor.Descriptor(
  name='StreamInfo',
  full_name='protos.StreamInfo',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='site', full_name='protos.StreamInfo.site', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=b"".decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='user', full_name='protos.StreamInfo.user', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=b"".decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='quality', full_name='protos.StreamInfo.quality', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=b"".decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='output_template', full_name='protos.StreamInfo.output_template', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=b"".decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=24,
  serialized_end=106,
)


_STREAMRESPONSE = _descriptor.Descriptor(
  name='StreamResponse',
  full_name='protos.StreamResponse',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  create_key=_descriptor._internal_create_key,
  fields=[
    _descriptor.FieldDescriptor(
      name='url', full_name='protos.StreamResponse.url', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=b"".decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
    _descriptor.FieldDescriptor(
      name='error', full_name='protos.StreamResponse.error', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR,  create_key=_descriptor._internal_create_key),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=108,
  serialized_end=152,
)

DESCRIPTOR.message_types_by_name['StreamInfo'] = _STREAMINFO
DESCRIPTOR.message_types_by_name['StreamResponse'] = _STREAMRESPONSE
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

StreamInfo = _reflection.GeneratedProtocolMessageType('StreamInfo', (_message.Message,), {
  'DESCRIPTOR' : _STREAMINFO,
  '__module__' : 'stream_pb2'
  # @@protoc_insertion_point(class_scope:protos.StreamInfo)
  })
_sym_db.RegisterMessage(StreamInfo)

StreamResponse = _reflection.GeneratedProtocolMessageType('StreamResponse', (_message.Message,), {
  'DESCRIPTOR' : _STREAMRESPONSE,
  '__module__' : 'stream_pb2'
  # @@protoc_insertion_point(class_scope:protos.StreamResponse)
  })
_sym_db.RegisterMessage(StreamResponse)


DESCRIPTOR._options = None

_STREAM = _descriptor.ServiceDescriptor(
  name='Stream',
  full_name='protos.Stream',
  file=DESCRIPTOR,
  index=0,
  serialized_options=None,
  create_key=_descriptor._internal_create_key,
  serialized_start=154,
  serialized_end=219,
  methods=[
  _descriptor.MethodDescriptor(
    name='GetStream',
    full_name='protos.Stream.GetStream',
    index=0,
    containing_service=None,
    input_type=_STREAMINFO,
    output_type=_STREAMRESPONSE,
    serialized_options=None,
    create_key=_descriptor._internal_create_key,
  ),
])
_sym_db.RegisterServiceDescriptor(_STREAM)

DESCRIPTOR.services_by_name['Stream'] = _STREAM

# @@protoc_insertion_point(module_scope)