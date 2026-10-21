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

    private static String read(String path) throws Exception {
        Path p = Paths.get(path);
        return new String(Files.readAllBytes(p), StandardCharsets.UTF_8);
    }
}
