# GOT Experiments Document

## Building

To build the examples, use `make all`:

``` eval
make all
```

Currently, this will avoid using the PLT as it isn't necessary if we're going to *eagerly* set up the GOT entries.

## PLT and GOT

Dynamic (shared) libraries enable

- the separate compilation of programs and libraries, and
- the sharing of read-only data in the libraries across programs that use it.

### PIC and PIE

When the dynamic library is linked with PIC, it also enables the code to be mapped into any virtual address, which has security benefits (and/or benefits for Janus).
Even the main program can be compiled as PIE to get some of the same benefits.

``` eval
objdump -S got_test | grep baz
```

This shows us an example of how the `baz` global variable is accessed from `main` when we use PIE.
Instead of accessing `baz` at a fixed address, we're instead accessing the memory at an offset from the `rip` (instruction pointer) register.
The binary assumes that the data/bss/text/etc sections are all set up contiguously in memory, so the offset from the instruction pointer to that global variable will always be something that is fixed.
Thus, no matter which virtual address the program is mapped at, the code can find `baz` by simply offsetting from `rip`.
Same thing for functions!

```eval
objdump -S got_test | grep local_fn
```

Note that even though `objdump` displays the address of the `local_fn` in the `call` instruction, the `e8` instruction actually uses a relative offset.
For example if the `call` instruction were `117a:       e8 aa ff ff ff`, the offset `aa ff ff ff` is little endian, and if we cast (`0xFFFFAA`) to an integer, it would be `-86`, and `0x117a - 86 = 0x1129`, which is the address of the `local_fn`.

If we look at the library, we see similar logic for variable and function access.

```eval
objdump -S libgot_lib.so | grep "<baz>"
```

Here we see access to a global variable within the shared library also uses the PC-relative addressing.

So the conclusion is: with PIC and PIE, we can place the library and executable in any virtual address.
This can be quite useful for us, and it gives us freedom in the booter to decide where objects should be loaded, and removes complexity from the build system.

### GOT

When we want to use a symbol in the library from the program, or a symbol in the program from the library, we have to jump through some hoops.
Neither binary can know at compile-time where the data or function is in the other binary as only the loader learns/knows that information.

```eval
objdump -S libgot_lib.so | grep -A 7 barfn
```

This is a function in the library that is accessing the `bar` variable which should use the GOT.
We can tell because when we access memory using `rip`-relative addressing (see PIC/PIE above), we only read out an address.
The next line has to dereference (recall that `mov (%rax), %eax` dereferences `%rax` and places the result in `%eax`) that value to find the actual global variable.
So accessing a global variable actually requires that we access a global variable *in the GOT*, then use that address to find the variable.

We can see that function calls can also use the GOT, for example when the main program (`got_test`) calls `foofn` in the library:

```eval
objdump -S got_test | grep foofn
```

Note that this doesn't require two instructions like the previous example as the `call` instruction enables the dereference operation as part of the instruction semantics (see the `*` at the start).

OK, so where is the GOT, and how is it accessed?
If we look at the dynamic relation information in the library...

```eval
readelf -r libgot_lib.so | grep -e foo -e rela.dyn
```


...and in the main program...

```eval
readelf -r got_test | grep -e foofn -e rela.dyn
```

...we see that we're being told that the symbols in the *other* binary have addresses at specific *offset*s (first column) into the binary.

First, lets look at the library:

```eval
readelf -t libgot_lib.so | grep -A 2 ".got"
```

The address (for `foo` in the `rela.dyn` section above) falls into the `.got` section we see here.
Similarly, the `foofn` in the main program falls into the `.got` section.

```eval
readelf -t got_test | grep -A 2 ".got"
```

These locations in the `.got` section designate where the pointers need to be populated by the loader for that specific symbol.

This means that all that we need to do when we load the objects, is figure out

1. where the GOT entries are for the symbols needed by the object, and
2. in which other object those symbols are defined, and what address we've loaded them.

With this, we can populate all of the GOT tables!

Form where we are, this will take:

1. separately adding libraries into the boot procedure, so that they can be separately loaded,
2. adding meta-data for components telling us which libraries they depend on,
3. parsing the elf objects to find out where the relation information is (where the GOT entries are to which symbols),
4. parsing the elf objects to find out where the exported symbols are, and
5. populating the GOTs with this information!

Not a small amount of work, but it certainly will clean up the entire library process.

### PLT

The PLT is a level of indirection to invoke functions in the other binary (i.e. the program calling the library functions).
When you call the desired function, you instead call a *trampoline* function that resolves how to call the real function.
The PLT enables the *lazy* setting of the addresses of those functions by the loader, only when they are called, instead of at load time.
We don't really want this ability.

The PLT also uses the GOT to locate the specific function addresses, so this PLT-level-of-indirection, *also* uses the GOT-level-of-indirection.
But you can compile with `-fno-plt`, yet while maintaining PIE/PLT and the GOT, to enable code generation that doesn't use the PLT, and instead directly uses the GOT instead of calling the trampoline.

The `Makefile` does this:

```eval
grep no-plt Makefile
```

## Copy Relocations

The linker does try to do some unexpected, interesting optimizations.
When global variables defined within the library, are directly accessed in the program, they *can be* moved into the data-section (or bss) of the program!
In this case, the program can access (using the PIC/PIE logic above) the library global variables!
It also means that we'll use the GOT in the library to access its own global variables that have been "copy relocated" into the program.

I don't know why, but these copy entries do appear in the dynamic relocation information:

```eval
readelf -r libgot_lib.so | grep -e  R_X86_64_COPY -e rela.dyn
```

```eval
readelf -r got_test | grep -e R_X86_64_COPY -e rela.dyn
```

In many cases, this will **copy** the global data so that the shared library has a copy, as does the program.
This is *bad* and I can't believe this is a default behavior.
We should likely just ensure that data is never directly accessed from a client.
But this is easier said than done as we have a lot of *inlined* functions that access library data.
I don't have a good solution to this.

The example we've created in this repo does *not* do this, though.
It seems to, by default, make it so that the global data in the library uses the GOT to instead be placed in the binary.
I *believe* this means that any non-`static` global variables in the library are, by default, placed in the executable.

This is a pending question.
Is a global, visible variable in a shared library always guaranteed to be placed in the program, or are there cases where multiple copies exist, or are there cases where it is kept in the shared library?
I don't know.

## Shared Libraries, `--gc-sections`, and Linker-script's `KEEP`

Shared libraries can be compiled with linker scripts, and `--gc-sections` can be used just the same.
However, the big question is how are the garbage-collection "roots" determined?
With shared libraries, it seems to make a very conservative assumption that anything that *can* be accessed outside of the library, *will be*, thus must be a root.
In other words, any symbols that are in the `.dynsym` and `.rela.dyn`/`.rel.dyn` sections will be considered roots.

So, if we wanted to make this really work, we'd have to use `objcopy` to make most (all) symbols that aren't `KEEP` be private, then use our custom crafted linker script to use `KEEP` to define the roots, and GC from there.

## Useful references

- https://maskray.me/blog/2021-08-29-all-about-global-offset-table
- https://maskray.me/blog/2021-09-19-all-about-procedure-linkage-table
- https://www.technovelty.org/linux/plt-and-got-the-key-to-code-sharing-and-dynamic-libraries.html
