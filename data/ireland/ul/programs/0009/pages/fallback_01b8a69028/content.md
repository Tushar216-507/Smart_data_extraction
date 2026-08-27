# C# ถามเรื่องเครื่องคิดเลขครับ คือผมสร้างเครื่องคิดเลขเฉพาะการบวกขึ้นครับ

โพสกระทู้ (
8 )
บทความ (
0 )

คือผมสร้างเครื่องคิดเลขเฉพาะการบวกขึ้นครับ ซึ่งหลักการเหมือนกับเครื่องคิดเลขทั่วไปๆ ซึ่งสามารถกดบวกเลขไปได้เรื่อยๆ ซึ่งข้อแตกต่างคือต้องเป็นการรับตัวเลขนั้นๆ มาจาก textbox อันเดียวครับ (โจทย์กำหนดมา) ผมทำได้แค่ให้มันรับมาแค่สองตัว ไม่ทราบจะมีวิธีไหนที่ให้มันรับตัวเลขได้ตลอดจนกว่าจะกดเคลียร์ครับ

นี่เป็นภาพโปรแกรมนะครับ

ส่วนนี่เป็นโค้ดของโปรแกรมตัวนี้ครับ
Code (C#)

```
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Windows.Forms;

namespace test
{
    public partial class Form1 : Form
    {
        public static int x, y, z;
        public Form1()
        {
            InitializeComponent();
        }

        private void button1_Click(object sender, EventArgs e)
        {
            x = Convert.ToInt32(textBox1.Text);
            textBox1.Clear();
            label1.Text = Convert.ToString(x);
        }

        private void button2_Click(object sender, EventArgs e)
        {
            y = Convert.ToInt32(textBox1.Text);
            z=x + y;
            label1.Text =Convert.ToString(x)  + " + " + Convert.ToString(y) + " = " + Convert.ToString(z);
            //textBox1.Text=Convert.ToString(x);
        }

        private void button3_Click(object sender, EventArgs e)
        {
            textBox1.Clear();
            label1.Text = "";
        }
    }
}
```

Tag : - - - -

Date :
2009-11-14 23:01:44
By :
princecoffee
View :
18014
Reply :
4

พอดี เขียน WinApp ไม่เป็นเลนเขียน C# WebApp มาให้นะครับ ลองประยุกดูและกัน เพราะ WebApp ผมจะใช้ Session ด้วย ไม่รู้ WinApp ใช้อะไร ^^

หน้า aspx
Code (C#)

```
<body>
    <form id="form1" runat="server">
    <div>
        &nbsp;<asp:Label ID="Label2" runat="server"></asp:Label>
    <asp:Label ID="Label1" runat="server"></asp:Label><br />
        <asp:TextBox ID="TextBox1" runat="server"></asp:TextBox>
        <asp:Button ID="btn_up" runat="server" Text="Insert" OnClick="btn_up_Click" />
        <asp:Button ID="btn_Add" runat="server" Text="+" OnClick="btn_Add_Click" />
        <asp:Button ID="btn_result" runat="server" Text="=" OnClick="btn_result_Click" />
        </div>
    </form>
</body>
```

Code Behind
Code (C#)

```
using System.Collections.Generic;
public partial class Calculate : System.Web.UI.Page
{
    public ArrayList inputData = new ArrayList();
    int result = 0;
    protected void Page_Load(object sender, EventArgs e)
    {

        if (Session["data"] != null)
        {
            inputData = (ArrayList)Session["data"];

        }
        if (Session["result"] != null)
        {
            result = (int)Session["result"];
        }

    }

    protected void btn_up_Click(object sender, EventArgs e)
    {
        inputData.Add(TextBox1.Text);
        int index = inputData.Count;
        if (index >= 3)
        {
            if (result == 0)
            {
                if (inputData[index - 2].ToString() == "+")
                {
                    result += System.Convert.ToInt32(inputData[index - 3].ToString()) + System.Convert.ToInt32(inputData[index - 1].ToString());
                    Session["result"] = result;

                }
            }
            else
            {
                result += System.Convert.ToInt32(inputData[index - 1].ToString());
                Session["result"] = result;
            }
        }

        Session["data"] = inputData;
        TextBox1.Text = "";
        Label2.Text = "";
        foreach (string a in inputData)
        {
            //Label1.Text +=""+ a;
            Label2.Text += "" + a;

        }

    }
    protected void btn_Add_Click(object sender, EventArgs e)
    {
        inputData.Add("+");
        Session["data"] = inputData;
        TextBox1.Text = "";
        Label2.Text = "";
        foreach (string a in inputData)
        {
            //Label1.Text +=""+ a;
            Label2.Text += "" + a;

        }
    }
    protected void btn_result_Click(object sender, EventArgs e)
    {
        inputData = (ArrayList)Session["data"];
        foreach(string a in inputData)
        {
            //Label1.Text +=""+ a;
            Label1.Text = "=" + result;

        }
    }
}
```

Date :
2009-11-19 13:48:04
By :
ksillapapan

Code (C#)

```
        private string number(string N)
        {
            if (textBox1.Text == "0")
                return N;
            else if (btnResult.Enabled == true)
                return textBox1.Text + N;
            else
            {
                btnResult.Enabled = true;
                listBox1.Items.Clear();
                return N;
            }

```

Date :
2011-12-16 14:55:07
By :
kkkkk

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
//int a;
bool plus = false;
bool minus = false;
bool multiply = false;
bool divide = false;
bool power = false;
public Form1()
{
InitializeComponent();
}

private void num\_0\_Click(object sender, EventArgs e)
{
textBox1.Text = textBox1.Text + "0";
}

private void num\_1\_Click(object sender, EventArgs e)
{
textBox1.Text = textBox1.Text + "1";
}

private void num\_2\_Click(object sender, EventArgs e)
{
textBox1.Text = textBox1.Text + "2";
}

private void num\_3\_Click(object sender, EventArgs e)
{
textBox1.Text = textBox1.Text + "3";
}

private void num\_4\_Click(object sender, EventArgs e)
{
textBox1.Text = textBox1.Text + "4";
}

private void num\_5\_Click(object sender, EventArgs e)
{
textBox1.Text = textBox1.Text + "5";
}

private void num\_6\_Click(object sender, EventArgs e)
{
textBox1.Text = textBox1.Text + "6";
}

private void num\_7\_Click(object sender, EventArgs e)
{
textBox1.Text = textBox1.Text + "7";
}

private void num\_8\_Click(object sender, EventArgs e)
{
textBox1.Text = textBox1.Text + "8";
}

private void num\_9\_Click(object sender, EventArgs e)
{
textBox1.Text = textBox1.Text + "9";
}

private void btnBackspace\_Click(object sender, EventArgs e)
{
int a = textBox1.Text.Length;
if (textBox1.Text == "")
{
textBox1.Text = "";
}

else
{
textBox1.Text = textBox1.Text.Remove(a - 1);
}
}

private void button1\_Click(object sender, EventArgs e)
{
if (plus)
{

decimal dec = Convert.ToDecimal(textBox1.Tag) + Convert.ToDecimal(textBox1.Text);

textBox1.Text = dec.ToString();

}

else if (minus)
{

decimal dec = Convert.ToDecimal(textBox1.Tag) - Convert.ToDecimal(textBox1.Text);

textBox1.Text = dec.ToString();

}

else if (multiply)
{

decimal dec = Convert.ToDecimal(textBox1.Tag) \* Convert.ToDecimal(textBox1.Text);

textBox1.Text = dec.ToString();

}

else if (divide)
{

if (textBox1.Text == "0")
{

textBox1.Text = "0";

}

else if (textBox1.Text != "0")
{

decimal dec = Convert.ToDecimal(textBox1.Tag) / Convert.ToDecimal(textBox1.Text);

textBox1.Text = dec.ToString();

}

}

else if (power)
{

decimal dec = Convert.ToDecimal(textBox1.Tag) \* Convert.ToDecimal(textBox1.Tag);

textBox1.Text = dec.ToString();
}

return;

}

private void btnKoon\_Click(object sender, EventArgs e)
{
if (textBox1.Text == "")
{

return;

}

else
{

multiply = true;

textBox1.Tag = textBox1.Text;

textBox1.Text = "";

}
}

private void btnLopp\_Click(object sender, EventArgs e)
{
if (textBox1.Text == "")
{

return;

}

else
{

minus = true;

textBox1.Tag = textBox1.Text;

textBox1.Text = "";
}
}

private void btnBuak\_Click(object sender, EventArgs e)
{
if (textBox1.Text == "")
{

return;

}

else
{

plus = true;

textBox1.Tag = textBox1.Text;

textBox1.Text = "";
}
}

private void btnHan\_Click(object sender, EventArgs e)
{
if (textBox1.Text == "")
{
return;
}

else
{
divide = true;
textBox1.Tag = textBox1.Text;
textBox1.Text = "";
}
}

private void btnClear\_Click(object sender, EventArgs e)
{
textBox1.Text = "";
}

private void btnJud\_Click(object sender, EventArgs e)
{
if (textBox1.Text.Contains("."))
{
return;
}
else
{
textBox1.Text = textBox1.Text + ".";
}
}
}
เอามาให้ดูครับ ใช่ได้เลย เห็นว่า ปีหนึ่งต้องใช่มัน ผมไม่เก่งหรอกแต่ อัลลกอล์ ผมแน่น เลยทำได้ ลองให้เพื่อนฝึกอัลกอล์ดูนะครับ

Date :
2012-09-14 15:28:36
By :
narutoyah