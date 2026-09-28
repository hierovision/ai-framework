# Language-specific security pitfalls

Unsafe/safe pairs for the languages a review is likely to touch. These are
starting points, not a complete list — a review should reason from the
language's memory model, type system, standard library, and ecosystem patterns
as well. Read only the section for the language under review; the pair is
illustrative, and the Step-6 triage rubric still decides whether a match is a
finding.

## Contents

- JavaScript / TypeScript
- Python
- Java
- C# / .NET
- PHP
- Go
- Ruby
- Rust
- C / C++
- Swift
- Kotlin
- Scala
- Shell (Bash)
- SQL (all dialects)
- PowerShell
- Elixir
- Perl
- Lua
- R
- Dart / Flutter

## JavaScript / TypeScript

Risks: prototype pollution, XSS, eval injection, `postMessage` trust.

```js
// UNSAFE — recursive merge reaches Object.prototype for every object.
deepMerge(config, JSON.parse(body));
// SAFE — skip dangerous keys at every depth (top-level stripping misses
// {"a": {"__proto__": ...}}), or schema-validate before merging.
const BLOCKED = new Set(["__proto__", "constructor", "prototype"]);
function safeMerge(target, src) {
  for (const k of Object.keys(src)) {
    if (BLOCKED.has(k)) continue;
    const v = src[k];
    if (v && typeof v === "object" && !Array.isArray(v)) {
      const cur = Object.hasOwn(target, k) ? target[k] : undefined;
      if (!cur || typeof cur !== "object" || Array.isArray(cur)) target[k] = {};
      safeMerge(target[k], v);
    } else {
      target[k] = v;
    }
  }
  return target;
}

// UNSAFE — code from data.
eval(userCode); new Function(userCode); setTimeout(userCode, 0);
// SAFE — never build executable code from input; use a table/dispatcher.
```

Watch for: `eval`, `new Function`, string args to timers, `innerHTML` /
`outerHTML` / `insertAdjacentHTML` / `document.write` / `dangerouslySetInnerHTML`,
`location`/`href` assignment from user input, `postMessage` handlers without an
`origin` check, `child_process.exec` with interpolated strings, `require`/
dynamic `import` of user-controlled paths, server-side template literals in
`res.send(\`...${user}\`)`.

## Python

Risks: pickle/deserialization RCE, format-string injection, SQL/shell
injection, SSTI.

```python
# UNSAFE — pickle is code execution.
pickle.loads(user_data)
# SAFE — JSON (or a schema-validated format) for untrusted data.
json.loads(user_data)

# UNSAFE — interpolation.
query = "SELECT * FROM users WHERE name = '%s'" % user_input
# SAFE — parameters.
cursor.execute("SELECT * FROM users WHERE name = %s", (user_input,))

# UNSAFE — the user controls the TEMPLATE
# ("{u.__class__.__init__.__globals__[SECRET]}" walks attributes).
user_template.format(u=user)
# SAFE — literal template, user data as an argument.
"Hello {name}".format(name=user_input)
```

Watch for: `pickle`, `yaml.load` without `SafeLoader`, `eval`/`exec`, `os.system`,
`subprocess(..., shell=True)`, `jinja2.Template(user_input)` (SSTI),
`__import__`, `tempfile.mktemp`, `requests` without timeouts, `assert` used for
security checks (stripped under `-O`), `random` for tokens.

## Java

Risks: deserialization RCE, XXE, JNDI injection, expression-language injection.

```java
// UNSAFE — arbitrary type materialization.
ObjectInputStream ois = new ObjectInputStream(userStream);
Object obj = ois.readObject();
// SAFE — schema-bound data binding, no polymorphic type metadata.
ObjectMapper mapper = new ObjectMapper();
mapper.readValue(json, SafeClass.class);
```

Watch for: `ObjectInputStream`, `Runtime.exec` / `ProcessBuilder` with user
input, `InitialContext.lookup` (JNDI), XML parsers without external entities
disabled, `ScriptEngine.eval`, `SpEL`/`OGNL` expressions from user input,
`MessageDigest.getInstance("MD5")` for passwords, `Math.random` for tokens,
permissive `SecurityManager` removal assumptions, commons-collections-style
gadget classes on the classpath.

## C# / .NET

Risks: deserialization, SQL string building, path traversal.

```csharp
// UNSAFE — BinaryFormatter is unsafe by design.
BinaryFormatter bf = new BinaryFormatter();
object obj = bf.Deserialize(stream);
// SAFE — System.Text.Json with a concrete type.
var obj = JsonSerializer.Deserialize<SafeType>(json);
```

Watch for: `BinaryFormatter`, `JavaScriptSerializer`, `TypeNameHandling.All`
/ `Auto`, `DataTable.ReadXml`, raw SQL string concatenation, `Path.Combine`
without validating traversal (`..`), `Process.Start` with user args,
`Random` class for tokens, `Request.Query`/form values passed to `SqlCommand`,
`ValidateRequest="false"` on views.

## PHP

Risks: type juggling, file inclusion, object injection, weak comparisons.

```php
// UNSAFE — "0e123" == "0e456" and similar magic-hash juggling.
if ($password == $stored_hash) { ... }
// SAFE — algorithm-aware, constant-time verification.
if (password_verify($password, $stored_hash)) { ... }
$hash = password_hash($password, PASSWORD_DEFAULT);
// Comparing two known strings (tokens, HMACs, webhook signatures):
if (hash_equals($expected_token, $provided_token)) { ... }

// UNSAFE — path/URL straight into an include.
include($_GET['page'] . '.php');
// SAFE — allowlist to a fixed set.
$allowed = ['home', 'about'];
include(in_array($page, $allowed, true) ? "$page.php" : 'home.php');
```

Watch for: `==` vs `===`, `include`/`require` with user input, `unserialize`,
`preg_replace` with `/e`, `extract`, `md5`/`sha1` for passwords, `rand` for
tokens, `file_get_contents` on user URLs (SSRF), `shell_exec`/`exec`/backticks,
`uploaded` files kept under the web root.

## Go

Risks: data races, `text/template` misuse, unchecked bounds, `unsafe`.

```go
// UNSAFE — unsynchronized counter.
go func() { counter++ }()
// SAFE — atomic/sync primitives.
atomic.AddInt64(&counter, 1)

// UNSAFE — marking user input as trusted HTML.
template.HTML(userInput)
// SAFE — let html/template escape it.
{{.UserInput}}
```

Watch for: `unsafe` package and pointer arithmetic, `text/template` where
`html/template` is required, race-prone shared state, `os/exec` with shell
strings, unchecked slice indexing on user-provided sizes, `math/rand` for
tokens, `http.Get` on user URLs without egress controls, `ioutil.ReadAll` on
unbounded input, `template.URL`/`JS`/`CSS` casts.

## Ruby

Risks: mass assignment, YAML deserialization, regex DoS, `send`.

```ruby
# UNSAFE — every param becomes an attribute.
User.new(params[:user])
# SAFE — strong parameters.
User.new(params.require(:user).permit(:name, :email))

# UNSAFE — YAML can instantiate arbitrary objects.
YAML.load(user_input)
# SAFE — no arbitrary classes.
YAML.safe_load(user_input)
```

Watch for: `YAML.load`, `Marshal.load`, `eval`/`instance_eval`/`class_eval`,
`send`/`public_send` with user input, `permit!`, `where("... #{input}")`,
`File.open` with user paths, `Open3`/backticks with interpolation, Rails
`redirect_to params[:url]`, `skip_before_action :verify_authenticity_token`.

## Rust

Risks: `unsafe` blocks, FFI boundaries, integer overflow in release,
panics on untrusted input.

```rust
// CAUTION — unsafe bypasses the guarantees.
unsafe { ptr::read(user_ptr) }

// CAUTION — overflow panics in debug and wraps silently in release.
let x: u8 = parse_user_len(input);
let y = x + 1;
// SAFE — make the overflow case explicit.
let y = x.checked_add(1).ok_or(Error::TooLarge)?;
```

Watch for: `unsafe` blocks without a documented invariant, FFI calls that
trust C-side lengths, `overflow-checks = false` in release with arithmetic on
untrusted values, `unwrap`/`expect`/array indexing on untrusted input (panic =
DoS), `std::process::Command` built from user input, `serde` deserializing
into enums with untrusted variants, secrets left in `Debug` output.

## C / C++

Risks: buffer overflow, use-after-free, format strings, integer overflow in
size math.

```c
/* UNSAFE — no bounds. */
char buf[10]; strcpy(buf, userInput);

/* ALSO UNSAFE — strncpy does not null-terminate when src >= n. */
strncpy(buf, userInput, sizeof(buf) - 1);

/* SAFE — snprintf always terminates and reports truncation. */
if (snprintf(buf, sizeof buf, "%s", userInput) >= (int)sizeof buf) {
    /* truncated — decide explicitly, do not ignore */
}

/* UNSAFE — format string. */
printf(userInput);
/* SAFE — fixed format. */
printf("%s", userInput);
```

Watch for: `strcpy`/`strcat`/`sprintf`/`gets`, `strncpy` termination,
`alloca`/`malloc` sized from untrusted values (check the multiply for
overflow), pointer arithmetic past allocation, use-after-free/double-free,
`system`/`popen`/`exec` with concatenated input, `setuid`/privilege-drop
mistakes, `memcpy` with untrusted lengths, signed/unsigned confusion in
bounds checks.

## Swift

Risks: force unwrapping on untrusted data (DoS), format strings, insecure
local storage.

```swift
// UNSAFE — crash on untrusted shape.
let value = jsonDict["key"]!
// SAFE — handle absence.
guard let value = jsonDict["key"] else { return }

// UNSAFE — user input as the format.
String(format: userInput, args)
// SAFE — fixed format string, data as argument.
```

Watch for: force unwrap `!`/`try!` on network or user data,
`String(format:)` with user input, `NSSecureCoding` misuse, secrets in
`UserDefaults`, ATS exceptions (`NSAllowsArbitraryLoads`), WebView bridges
that expose native methods to remote content.

## Kotlin

Risks: Java-interop null safety bypass, reflection, serialization.

```kotlin
// UNSAFE — platform type can be null despite the type.
val len = javaString.length
// SAFE — explicit null handling.
val len = javaString?.length ?: 0

// UNSAFE — reflection on user input.
clazz.getDeclaredMethod(userInput)
// SAFE — allowlist of callable methods.
```

Watch for: `!!` on Java-interop/platform types, reflection with user input,
`readObject`/serialization, WebView `addJavascriptInterface` (pre-API-17
classic), exported Activities/Services without permission checks,
`WorldReadable`/`WorldWritable` files, insecure `SharedPreferences` for
secrets.

## Scala

Risks: XML external entities, Java serialization, pattern-match
exhaustiveness.

```scala
// UNSAFE — external entities resolved.
val xml = XML.loadString(userInput)
// SAFE — disable external entity resolution on the parser.
val factory = SAXParserFactory.newInstance()
factory.setFeature("http://xml.org/sax/features/external-general-entities", false)
```

Watch for: Java-interop issues (see Java), `scala.xml` parsing untrusted
input, `Serializable`/Java serialization, non-exhaustive matches reaching a
`MatchError`, Play/Akka routes without authorization, `&&`/`||` logic that
skips an authz check.

## Shell (Bash)

Risks: command injection, word splitting, globbing, `eval`.

```bash
# UNSAFE — unquoted variable splits and globs.
rm $user_file
# SAFE — quote it.
rm -- "$user_file"

# UNSAFE — code from data.
eval "$user_command"
# SAFE — never eval input; use a case statement.
```

Watch for: unquoted expansions, `eval`, backticks, `$(...)` with user input,
missing `set -euo pipefail`, `curl | sh` installs, `chmod 777`, credentials
in command lines (visible in `ps`) or shell history, `mktemp` misuse,
`--` missing before user paths, temporary files in shared directories.

## SQL (all dialects)

Risks: injection, privilege escalation, data exfiltration via dynamic SQL.

```sql
-- UNSAFE — concatenated literal.
"SELECT * FROM users WHERE id = " + userId
-- SAFE — a prepared statement with a bound parameter (language-specific).
```

Watch for: dynamic SQL (`EXECUTE IMMEDIATE`, `EXECUTE`), stored procedures
assembling queries, `ORDER BY`/table/column names taken from input (cannot be
parameterized — allowlist them), ORM raw fragments, database users with
broader grants than the app needs, `SECURITY DEFINER` functions without a
pinned `search_path`, RLS policies that widen visibility (`USING (true)`),
row ownership checks missing from policy predicates.

## PowerShell

Risks: command injection, execution-policy circumvention, unvalidated paths.

```powershell
# UNSAFE — code from data.
Invoke-Expression $userInput
# SAFE — avoid Invoke-Expression with user data; call the cmdlet directly.

# UNSAFE — unvalidated path.
Get-Content $userPath
# SAFE — validate the path stays within an allowed directory.
```

Watch for: `Invoke-Expression`, `& $userVar`, `Start-Process` with user args,
`-ExecutionPolicy Bypass`, `Add-Type` compiling user input, credentials in
script parameters/logs, `ConvertTo-SecureString -AsPlainText`, remote
downloads piped to execution.

## Elixir

Risks: atom exhaustion, code evaluation, unsafe term deserialization.

```elixir
# UNSAFE — unbounded atom creation from input.
String.to_atom(user_input)
# SAFE — only pre-existing atoms.
String.to_existing_atom(user_input)

# UNSAFE — code from data.
Code.eval_string(user_input)
# SAFE — never evaluate input.
```

Watch for: `String.to_atom`, `Code.eval_string`/`Code.eval_quoted`,
`:erlang.binary_to_term` without `:safe`, public/ETS tables exposed to
untrusted writers, Phoenix routes without plugs enforcing authorization,
`Phoenix.Token` misuse, SQL via `Ecto.Adapters.SQL.query` with interpolation.

## Perl

Risks: regex injection/DoS, two-argument `open`, taint-mode bypass.

```perl
# UNSAFE — user-supplied regex.
$input =~ /$user_pattern/;
# SAFE — quote metacharacters.
$input =~ /\Q$user_pattern\E/;

# UNSAFE — two-argument open lets the mode come from the filename.
open(FILE, $user_file);
# SAFE — explicit mode handle.
open(my $fh, '<', $user_file);
```

Watch for: two-arg `open`, regex from user input (ReDoS), backticks/`system`
with interpolation, `eval` in string form, disabled taint mode, `sprintf` with
user format, cookies/session ids from the client trusted directly.

## Lua

Risks: sandbox escape via `loadstring`, `os`/`io` exposure.

```lua
-- UNSAFE — code from data.
loadstring(user_code)()
-- SAFE — do not load untrusted code; if unavoidable, a restricted
-- environment that removes os/io/debug/load* entirely.
```

Watch for: `loadstring`/`load`/`loadfile`/`dofile` on untrusted input,
`os.execute`/`io` available to sandboxed code, `debug` library exposure,
`setfenv`/`_ENV` escapes, Nginx/OpenResty modules reading user files,
`string.format` with user format.

## R

Risks: code injection via `parse`/`eval`, path manipulation, `system`.

```r
# UNSAFE — data parsed as code.
eval(parse(text = user_input))
# SAFE — never parse input as code.

# UNSAFE — unvalidated path.
read.csv(paste0("data/", user_file))
# SAFE — validate the filename against a strict pattern.
if (grepl("^[a-zA-Z0-9]+\\.csv$", user_file)) read.csv(file.path("data", user_file))
```

Watch for: `eval(parse(...))`, `source` on user paths, `system`/`system2`
with input, `dplyr::sql`/`dbplyr` raw SQL, Shiny inputs used unvalidated in
queries, serialized `.rds`/`.RData` from untrusted sources, `download.file`
on user URLs.

## Dart / Flutter

Risks: insecure local storage, platform-channel trust, WebView bridges.

```dart
// UNSAFE — tokens in plain preferences.
prefs.setString('auth_token', token);
// SAFE — platform secure storage.
secureStorage.write(key: 'auth_token', value: token);
```

Watch for: secrets in `SharedPreferences`/plain files, `dart:mirrors` /
`Function.apply` on dynamic input, platform-channel data trusted without
validation, `WebView` JavaScript bridges exposing native methods, disabled
TLS verification (`badCertificateCallback`), deep links / intents without
validation, exported Android components (manifest) with no permission guard.

## Sources consulted

The language pairs above were adapted from the candidate material recorded in
[provenance.md](provenance.md), cross-checked against the language ecosystems'
standard guidance. They are illustrative, not exhaustive: reason from the
language's own model rather than treating this list as complete.
