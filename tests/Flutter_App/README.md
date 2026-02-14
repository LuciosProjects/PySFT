# PySFT HTTP Client (Dart)

Minimal Dart client to test the PySFT HTTP gateway.

## Run

From this folder:

```sh
dart pub get
dart run bin/main.dart
```

By default, the client starts the PySFT HTTP server on startup and then calls
`/health`. You can disable that with `--no-server`, or keep it running with
`--keep-server`.

To call the fetch endpoint:

```sh
dart run bin/main.dart --mode fetch
```

## Notes

If you want to run the server yourself, start it from the repo root:

```sh
python -m pysft.http_api

Then run the client with:

```sh
dart run bin/main.dart --no-server
```
```
