import org.openrewrite.InMemoryExecutionContext;
import org.openrewrite.python.internal.LockFileRegeneration;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * Drives one native lock engine from the command line.
 * Usage: Harness &lt;uv|pipenv|poetry|pdm&gt; &lt;original-manifest&gt; &lt;edited-manifest&gt; &lt;old-lock&gt; &lt;out-lock&gt;
 * Exit 0: success (lock written to out-lock); 2: structured failure (printed); 3: crash.
 */
public final class Harness {
    public static void main(String[] args) throws Exception {
        if (args.length != 5) {
            System.err.println("usage: Harness <uv|pipenv|poetry|pdm> <original-manifest> <edited-manifest> <old-lock> <out-lock>");
            System.exit(64);
        }
        LockFileRegeneration engine;
        switch (args[0]) {
            case "uv": engine = LockFileRegeneration.UV; break;
            case "pipenv": engine = LockFileRegeneration.PIPENV; break;
            case "poetry": engine = LockFileRegeneration.POETRY; break;
            case "pdm": engine = LockFileRegeneration.PDM; break;
            default: throw new IllegalArgumentException(args[0]);
        }
        String original = read(args[1]);
        String edited = read(args[2]);
        String oldLock = read(args[3]);
        long start = System.nanoTime();
        LockFileRegeneration.Result result;
        try {
            org.openrewrite.ExecutionContext ctx = new InMemoryExecutionContext(t -> {
                System.err.println("CTX_ERROR " + t);
            });
            if (System.getenv("PYLOCK_RECORD_HTTP") != null) {
                org.openrewrite.HttpSenderExecutionContextView http = org.openrewrite.HttpSenderExecutionContextView.view(ctx);
                http.setHttpSender(new RecordingHttp(http.getHttpSender(), Paths.get(System.getenv("PYLOCK_RECORD_HTTP"))));
            }
            if (System.getenv("PYLOCK_UV_VERSION") != null) {
                org.openrewrite.python.PythonExecutionContextView.view(ctx).setUvVersion(System.getenv("PYLOCK_UV_VERSION"));
            }
            result = engine.regenerate(edited, original, oldLock, ctx);
        } catch (Throwable t) {
            System.out.println("STATUS crash");
            System.out.println("CRASH " + t);
            t.printStackTrace(System.out);
            System.exit(3);
            return;
        }
        long ms = (System.nanoTime() - start) / 1_000_000;
        if (result.isSuccess() && result.getLockFileContent() != null) {
            Files.write(Paths.get(args[4]), result.getLockFileContent().getBytes(StandardCharsets.UTF_8));
            System.out.println("STATUS success");
            if (result.getDetail() != null) {
                System.out.println("DETAIL " + result.getDetail());
            }
            System.out.println("MILLIS " + ms);
            System.exit(0);
        }
        System.out.println("STATUS failure");
        LockFileRegeneration.Failure f = result.getFailure();
        if (f != null) {
            System.out.println("REASON " + f.getReason());
            System.out.println("PACKAGE " + f.getPackageName());
            System.out.println("INDEX " + f.getIndexUrl());
            System.out.println("DETAIL " + f.getDetail());
        } else {
            System.out.println("MESSAGE " + result.getErrorMessage());
        }
        System.out.println("MILLIS " + ms);
        System.exit(2);
    }

    /**
     * Saves every response the engine receives under the names the offline tests serve: a listing URL ending in
     * {@code /} as {@code <name>-listing-json} or {@code -listing-html}, any other URL by its last path segment, and
     * each URL answered 404 as a line of {@code 404}.
     */
    static final class RecordingHttp implements org.openrewrite.ipc.http.HttpSender {
        private final org.openrewrite.ipc.http.HttpSender delegate;
        private final Path dir;

        RecordingHttp(org.openrewrite.ipc.http.HttpSender delegate, Path dir) {
            this.delegate = delegate;
            this.dir = dir;
        }

        @Override
        public Response send(Request request) {
            String url = request.getUrl().toString();
            try (Response response = delegate.send(request)) {
                byte[] body = response.getBodyAsBytes();
                Files.createDirectories(dir);
                if (response.getCode() == 404) {
                    Files.write(dir.resolve("404"), (url + "\n").getBytes(StandardCharsets.UTF_8),
                            java.nio.file.StandardOpenOption.CREATE, java.nio.file.StandardOpenOption.APPEND);
                } else if (response.getCode() == 200) {
                    Files.write(dir.resolve(name(url, body)), body);
                }
                return new Response(response.getCode(), new java.io.ByteArrayInputStream(body), () -> {
                });
            } catch (java.io.IOException e) {
                throw new java.io.UncheckedIOException(e);
            }
        }

        static String name(String url, byte[] body) {
            String path = url.replaceFirst("[?#].*$", "");
            if (path.endsWith("/")) {
                String trimmed = path.substring(0, path.length() - 1);
                boolean json = body.length > 0 && body[0] == '{';
                return trimmed.substring(trimmed.lastIndexOf('/') + 1) + (json ? "-listing-json" : "-listing-html");
            }
            return path.substring(path.lastIndexOf('/') + 1);
        }
    }

    private static String read(String path) throws Exception {
        Path p = Paths.get(path);
        return new String(Files.readAllBytes(p), StandardCharsets.UTF_8);
    }
}
