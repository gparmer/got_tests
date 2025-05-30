#include <stdio.h>

extern int foo, bar;
int foofn(void);
int barfn(void);
int baz = 10;
extern const int fizzbuzz;

__attribute__((noinline)) void local_fn(void) { return; }

int
main(void)
{
	foofn();
	barfn();
	printf("%d %d %d %d\n", foo, bar, baz, fizzbuzz);
	local_fn();

	return 0;
}
