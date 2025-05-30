LIBFLAGS = -fPIC -fno-plt
MAINFLAGS = -fPIE -pie -fno-plt

all: got_lib.so got_test

got_lib.so: got_lib.c
	gcc -c $(LIBFLAGS) $^ -o $^.o
	gcc -shared -o lib$@ $^.o

got_test: got_test.c got_lib.so
	gcc $(MAINFLAGS) $< -o $@ -L. -lgot_lib

run: got_test
	LD_LIBRARY_PATH=.:$LD_LIBRARY_PATH ./got_test

doc: doc.md
	python3 docgen.py $< > doc.output.md

clean:
	rm -f libgot_lib.so got_lib.c.o got_test
