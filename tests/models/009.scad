function res() = 123;
module t() {
	a=10;
	b=20;
	c=8;
	d=2;

	res = function () a+b-c/d;

	module u() {

		a=100;
		b=200;
		c=80;
		d=20;

		result=res();
		cube([result,1,1]);
	}
	u();
} 
t();
