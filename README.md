# ClausIA AI

## gRPC Usage (Generated services)

1. Install deps:
```
pip install -r requirements.txt
```

2. Generate gRPC code:
```
python -m grpc_tools.protoc -I proto --python_out=. --grpc_python_out=. proto/clausia.proto
```

3. Run gRPC server:
```
python grpc_server.py
```

4. Example client usage is in `grpc_client_example.py`.


