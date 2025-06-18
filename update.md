# Compiler/Linker Options Experiments Document

##Hypothesis check
Hypothesis about the compiler/linker option that are confirmed:
-fPIC and -fno-plt make external data and function access go via GOT
-fPIC and -fno-plt causes relocation for external data and function symbols to be placed in .rela.dyn 
-fPIC and -shared make the undefined symbols are included in .dynsym section of shared file
-fPIE and -pie make the undefined symbols are included in .dynsym section of executable file
-fPIC and -pie make the undefined symbols are included in .dynsym section of executable file
-fPIC and -shared make symbols act as GC roots, preventing garbage collection even with -ffunction-sections / -fdata-sections
-fPIC and -shared will not make hidden symbols GC roots, if hidden symbols are not referenced internally, they can be garbage collected during linking
-fPIE is not the same as -fPIC , -fPIE may use direct calls or PC-relative addressing without going through GOT

###-fPIC and -fPIE
When we build a shared library with the compiler option -fPIC, the relocation-related code looks like this:

```asm
   8:	48 8b 05 00 00 00 00 	mov    0x0(%rip),%rax        # f <main+0xf>
			b: R_X86_64_REX_GOTPCRELX	a-0x4
   f:	8b 00                	mov    (%rax),%eax
  11:	89 c6                	mov    %eax,%esi
```

This shows that internal global data is accessed via the Global Offset Table (GOT). 

```asm
  28:	ff 15 00 00 00 00    	call   *0x0(%rip)        # 2e <external_func+0x13>
			2a: R_X86_64_GOTPCRELX	internal_func-0x4
```  

This shows that internal functions call is accessed via the GOT. 
The reason why a shared library access its own data and symbol via the GOT is that because the ELF symbol preemption(interpostion, LD_PRELOAD) rules require supporting runtime replacement. 

When we build executable file with compiler option -fPIE, the relocation related assembly code is below:

```asm
   8:	8b 05 00 00 00 00    	mov    0x0(%rip),%eax        # e <main+0xe>
			a: R_X86_64_PC32	a-0x4
   e:	89 c6                	mov    %eax,%esi
```

This shows that the executable file access the global data without go via GOT. 

###Copy Relocation
When an executable is built with -fPIE and linked with -pie, and it accesses a global data symbol defined in a shared library, the linker may allocate space for that data symbol in the executable itself. 

For example, the symbol from shared library might appear in the executable like this:
```nm
	0000004010 B a
```
This happens because, due to potential symbol preemption (e.g., via LD_PRELOAD), the linker cannot determine definitively which version of the data symbol will be used at runtime.

###Garbage-Collection on shared library
By default, symbols in a shared library are considered GC roots. This means garbage collection (via --gc-sections) will not remove them, even if they are not referenced.

To enable garbage collection of unused symbols in a shared library, we shall mark them as local using a version script below:
```
{
    global:
        exported_func;
        global_var1;
    local:
        *;
};
```
Then build with option --version-script=

###LTO Inline optimization
####Inline Optimization in Executables
#####Single source file:
if we build with gcc -O2 *.c -o *.out, no inline optimization. 
if we build with gcc -O2 -flto *.c -o *.out. helper function will be inlined.
#####Multiple source files:
The same as the single source file
####Inline Optimization in shared library
In a shared library, a callee function marked as local can be inlined when build with code gen option -flto. Global functions can not be inlined even with option -flto and also can not be removed even with option --gc-section. GOT includes no local symbols. 

###GOT on shared library
1. non-local callee function in the shared library are in the GOT when build with option "-fno-plt"(also not in got.plt)
2. non-local data in the shared library are always accessed through the GOT.
3. non-local callee function in the shared library can be inlined when build with option "-flto"
4. Local (hidden or static) functions or data will not appear in the GOT
5. non referenced global functions in the shared library are not in the GOT or GOT.PLT when build with option "-fno-plt"(also not in got.plt) 

###object file level
1. hidden all the symbols then re-export with a version script 
2. add keep list in the linker script
3. rebuild the shared library 

###elf file level 
1. using objcopy --localize-symbol=* on shared library will set the symbol as local but will not impact the GOT 
2. using objcopy --strip-symbol=* on shared library will remove the symbol but will not impact the GOT
3. -Wl,--unique=.text.* -Wl,--unique=.data.* enable the elf file generated with seperate function and data sections, to remove section, we need to remove both .rela.text.* and .text.*, and also symbol *. 

