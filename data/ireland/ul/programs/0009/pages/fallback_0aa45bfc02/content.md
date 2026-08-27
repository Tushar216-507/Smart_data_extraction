using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;

namespace WindowsFormsApplication1
{
public partial class Form1 : Form
{
float num1, num2, ans;
string strnum1="",strnum2="";
int even=0;
int count = 0;
bool status = false;
public Form1()
{
InitializeComponent();
}

private void button11\_Click(object sender, EventArgs e)
{
if (count == 0 )
{
strnum1 = strnum1 + ".";
txtNum1.Text = strnum1;

}
else
{
strnum2 = strnum2 + ".";
txtNum2.Text = strnum2;
count = 2;
}
}

private void button12\_Click(object sender, EventArgs e)
{
num1 = float.Parse(strnum1);
num2 = float.Parse(strnum2);
switch(even)
{
case 1:
ans = num1 / num2;
break;
case 2:
ans = num1 \* num2;
break;
case 3:
ans = num1 - num2;
break;
case 4:
ans = num1 + num2;
break;
default:
MessageBox.Show("Error นะจ๊ะ", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
break;

}
txtAns.Text = ans.ToString() ;
status = false;
btnsub.Enabled = true ;
btnshare.Enabled = true ;
btnmul.Enabled = true ;
btnadd.Enabled = true ;
count = 2;
}

private void button2\_Click(object sender, EventArgs e)
{
if (count == 0 )
{
if (strnum1 == "0")
{
strnum1 = "";
}
strnum1 = strnum1 + 8;
txtNum1.Text = strnum1;

}
else
{
if (strnum2 == "0")
{
strnum2 = "";
}
strnum2 = strnum2 + 8;
txtNum2.Text = strnum2;
count = 2;
}
}

private void Form1\_Load(object sender, EventArgs e)
{

}

private void button7\_Click(object sender, EventArgs e)
{
if (count == 0 )
{
if (strnum1 == "0")
{
strnum1 = "";
}
strnum1 = strnum1 + 1;
txtNum1.Text = strnum1;

}
else
{
if (strnum2 == "0")
{
strnum2 = "";
}
strnum2 = strnum2 + 1;
txtNum2.Text = strnum2;
count = 2;
}
}

private void button9\_Click(object sender, EventArgs e)
{
if (count == 0 )
{
if (strnum1 == "0")
{
strnum1 = "";
}
strnum1 = strnum1 + 3;
txtNum1.Text = strnum1;

}
else
{
if (strnum2 == "0")
{
strnum2 = "";
}
strnum2 = strnum2 + 3;
txtNum2.Text = strnum2;
count = 2;
}
}

private void button13\_Click(object sender, EventArgs e)
{
if (count == 2)
{

txtNum1.Text = txtAns.Text;
strnum1 = txtAns.Text;
strnum2 = "";
txtAns.Text = "";
txtNum2.Text = "";

}
even = 1;
txtEven.Text = "/";
btnmul.Enabled = false;
btnadd.Enabled = false;
btnsub.Enabled = false;
status = true;
if (count == 2)
{
count = 2;
}
else
{
count = 1;
}
}

private void btn7\_Click(object sender, EventArgs e)
{
if (count == 0 )
{
if (strnum1 == "0")
{
strnum1 = "";
}
strnum1 = strnum1 + 7;
txtNum1.Text = strnum1;

}
else
{
if (strnum2 == "0")
{
strnum2 = "";
}
strnum2 = strnum2+7;
txtNum2.Text = strnum2;
count = 2;
}
}

private void btn9\_Click(object sender, EventArgs e)
{
if (count == 0 )
{
if (strnum1 == "0")
{
strnum1 = "";
}
strnum1 = strnum1 + 9;
txtNum1.Text = strnum1;

}
else
{
if (strnum2 == "0")
{
strnum2 = "";
}
strnum2 = strnum2 + 9;
txtNum2.Text = strnum2;
count = 2;
}
}

private void btn4\_Click(object sender, EventArgs e)
{
if (count == 0 )
{
if (strnum1 == "0")
{
strnum1 = "";
}
strnum1 = strnum1 + 4;
txtNum1.Text = strnum1;

}
else
{
if (strnum2 == "0")
{
strnum2 = "";
}
strnum2 = strnum2 + 4;
txtNum2.Text = strnum2;
count = 2;
}
}

private void btn5\_Click(object sender, EventArgs e)
{
if (count == 0 )
{
if (strnum1 == "0")
{
strnum1 = "";
}
strnum1 = strnum1 + 5;
txtNum1.Text = strnum1;

}
else
{
if (strnum2 == "0")
{
strnum2 = "";
}
strnum2 = strnum2 + 5;
txtNum2.Text = strnum2;
count = 2;
}
}

private void btn6\_Click(object sender, EventArgs e)
{
if (count == 0 )
{
if (strnum1 == "0")
{
strnum1 = "";
}
strnum1 = strnum1 + 6;
txtNum1.Text = strnum1;

}
else
{
if (strnum2 == "0")
{
strnum2 = "";
}
strnum2 = strnum2 + 6;
txtNum2.Text = strnum2;
count = 2;
}
}

private void btn2\_Click(object sender, EventArgs e)
{
if (count == 0 )
{
if (strnum1 == "0")
{
strnum1 = "";
}
strnum1 = strnum1 + 2;
txtNum1.Text = strnum1;

}
else
{
if (strnum2 == "0")
{
strnum2 = "";
}
strnum2 = strnum2 + 2;
txtNum2.Text = strnum2;
count = 2;
}
}

private void button0\_Click(object sender, EventArgs e)
{
if (count == 0 )
{
strnum1 = strnum1 + 0;
txtNum1.Text = strnum1;

}
else
{
strnum2 = strnum2 + 0;
txtNum2.Text = strnum2;
count = 2;
}
}

private void textBox1\_TextChanged(object sender, EventArgs e)
{

}

private void btnC\_Click(object sender, EventArgs e)
{
even = 0;
count = 0 ;
btnsub.Enabled = true;
btnshare.Enabled = true;
btnmul.Enabled = true;
btnadd.Enabled = true;
txtNum1.Text = "";
txtNum2.Text = "";
txtEven.Text = "";
txtAns.Text = "";
strnum1 = "";
strnum2 = "";
num1 = 0;
num2 = 0;
ans = 0;
}

private void btnmul\_Click(object sender, EventArgs e)
{
if (count ==2 )
{

txtNum1.Text = txtAns.Text;
strnum1 = txtAns.Text;
strnum2 = "";
txtAns.Text = "";
txtNum2.Text = "";
}
even = 2;
txtEven.Text = "\*";
btnshare.Enabled = false;
btnadd.Enabled = false;
btnsub.Enabled = false;
status = true;
if (count == 2)
{
count = 2;
}
else
{
count = 1;
}
}

private void btnsub\_Click(object sender, EventArgs e)
{
if (count == 2)
{

txtNum1.Text = txtAns.Text;
strnum1 = txtAns.Text;
strnum2 = "";
txtAns.Text = "";
txtNum2.Text = "";
}
even = 3;
txtEven.Text = "-";
btnshare.Enabled = false;
btnmul.Enabled = false;
btnadd.Enabled = false;
status = true;
if (count == 2)
{
count = 2;
}
else
{
count = 1;
}

}

private void btnadd\_Click(object sender, EventArgs e)
{
if (count ==2)
{

txtNum1.Text = txtAns.Text;
strnum1 = txtAns.Text;
strnum2 = "";
txtAns.Text = "";
txtNum2.Text = "";
}
even = 4;
txtEven.Text = "+";
btnsub.Enabled = false;
btnshare.Enabled = false;
btnmul.Enabled = false;
status = true;
if (count == 2)
{
count = 2;
}
else
{
count = 1;
}
}

private void btnbs\_Click(object sender, EventArgs e)
{
int lengthstr,lengthsub;
if (status == true)
{
if (count == 2)
{
if (txtNum2.Text == "")
{
count = 1;
}
else
{
lengthstr = strnum2.Length;
lengthsub = lengthstr - 1;
strnum2 = strnum2.Remove(lengthsub, 1);
txtNum2.Text = strnum2;
}
}

else
{
txtEven.Text = "";
btnsub.Enabled = true;
btnshare.Enabled = true;
btnmul.Enabled = true;
btnadd.Enabled = true;
status = false;
}
}
else
{
if ((count == 0)||(count==1))
{
if (txtNum1.Text == "")
{
MessageBox.Show("โปรดระบุเลขในช่อง Num1", "Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
}
else
{
lengthstr = strnum1.Length;
lengthsub = lengthstr - 1;
strnum1 = strnum1.Remove(lengthsub, 1);
txtNum1.Text = strnum1;
}

}

else
if(count ==2)
{
lengthstr = strnum2.Length;
lengthsub = lengthstr - 1;
strnum2 = strnum2.Remove(lengthsub, 1);
txtNum2.Text = strnum2;
}
}

}
}
}

Date :
2011-11-11 16:21:45
By :
pridsada001