import 'dart:developer';
import 'dart:async';
import 'dart:io';

import 'package:http/http.dart' as http;

Future<void> main(List<String> args) async {
  final baseUrl = _argValue(args, '--base') ?? 'http://127.0.0.1:8000';
  final mode = _argValue(args, '--mode') ?? 'health';
  final keepServer = args.contains('--keep-server');
  final noServer = args.contains('--no-server');
  final pythonOverride = _argValue(args, '--python');

  Process? server;
  if (!noServer) {
    server = await _startPySftServer(pythonOverride);
    final ready = await _waitForHealth(baseUrl);
    if (!ready) {
      stderr.writeln('Server did not become ready in time.');
      if (!keepServer) {
        server.kill(ProcessSignal.sigterm);
      }
      exitCode = 1;
      return;
    }
  }

  final uri = switch (mode) {
    'fetch' => Uri.parse(
        '$baseUrl/fetch?indicators=MSFT,AAPL&attributes=price,volume&period=1m'),
    _ => Uri.parse('$baseUrl/health'),
  };

  try {
    final response = await http.get(uri);
    stdout.writeln('GET $uri');
    stdout.writeln('Status: ${response.statusCode}');
    stdout.writeln(response.body);
  } catch (error) {
    stderr.writeln('Request failed: $error');
    exitCode = 1;
  } finally {
    if (server != null && !keepServer) {
      server.kill(ProcessSignal.sigterm);
    }
  }
}

Future<Process> _startPySftServer(String? pythonOverride) async {
  final repoRoot = _repoRoot();
  final srcPath = '$repoRoot/src';
  final python = await _resolvePythonExecutable(pythonOverride, repoRoot);
  final environment = Map<String, String>.from(Platform.environment);
  final existingPythonPath = environment['PYTHONPATH'];
  environment['PYTHONPATH'] = existingPythonPath == null || existingPythonPath.isEmpty
      ? srcPath
      : '$srcPath:${existingPythonPath}';

  stdout.writeln('Using Python: $python');
  stdout.writeln('Repo root:    $repoRoot');
  stdout.writeln('PYTHONPATH:   ${environment["PYTHONPATH"]}');

  final process = await Process.start(
    python,
    ['-m', 'pysft.http_api'],
    workingDirectory: repoRoot,
    environment: environment,
    mode: ProcessStartMode.detachedWithStdio,
  );

  process.stdout.transform(SystemEncoding().decoder).listen(stdout.write);
  process.stderr.transform(SystemEncoding().decoder).listen(stderr.write);
  return process;
}

Future<bool> _waitForHealth(String baseUrl) async {
  final healthUri = Uri.parse('$baseUrl/health');
  const attempts = 30;
  for (var i = 0; i < attempts; i += 1) {
    try {
      final response = await http.get(healthUri);
      if (response.statusCode == 200) {
        return true;
      }
    } catch (_) {
      // Retry until the server is ready.
    }
    await Future<void>.delayed(const Duration(milliseconds: 500));
  }
  return false;
}

String? _argValue(List<String> args, String name) {
  final index = args.indexOf(name);
  if (index == -1 || index + 1 >= args.length) {
    return null;
  }
  return args[index + 1];
}

String _repoRoot() {
  final scriptFile = File.fromUri(Platform.script);
  final binDir = scriptFile.parent;
  final flutterAppDir = binDir.parent;
  final testsDir = flutterAppDir.parent;
  return testsDir.parent.path;
}

Future<String> _resolvePythonExecutable(String? cliPython, String repoRoot) async {
  final venvPython = '$repoRoot/.venv/bin/python';
  final envPython = Platform.environment['PYSFT_PYTHON'];
  final candidates = [
    if (cliPython != null) cliPython,
    if (envPython != null && envPython.isNotEmpty) envPython,
    venvPython,
    'python',
    'python3',
  ];

  for (final candidate in candidates) {
    try {
      final result = await Process.run(candidate, ['--version']);
      if (result.exitCode == 0) {
        return candidate;
      }
    } catch (_) {
      // Try next candidate.
    }
  }

  stderr.writeln('Python executable not found.');
  stderr.writeln('Set PYSFT_PYTHON or pass --python /path/to/python.');
  exit(1);
}
