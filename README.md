# Piston Bot

I can run Code inside Discord Chats.

![helloworld picture](helloworld.png)

You can add me to your server here: https://emkc.org/run 

I use https://github.com/engineer-man/piston to run code.

# How to use
You can use the bot like this 
````
/run <language>
```
<your code>
```
````

````
/run 
```<language>
<your code>
```
````

````
/run <language>
```<language>
<your code>
```
````

````
/run <language>
```<your code>
```
````

You can edit your last **/run** message if you make a mistake and the bot will edit it's initial response.

# What's new

## 2020-07-16
Made writing java code "snippets" easier (Thanks https://github.com/Minecraftian14)

When typing Java code the boilerplate code for `public class` will be added automatically.
````java
/run java
```
import java.util.List;
List.of(args).forEach(System.out::println);
```
````
will be interpreted as
````java
/run java
```
import java.util.List;
public class temp extends Object {
  public static void main(String[] args) {
    List.of(args).forEach(System.out::println);
  }
}
```
````


## 2020-07-15
Added optional command line parameters
You can use them by specifying them before the codeblock (1 per line)  

Example:
````
/run <language>
parameter 1
parameter 2
```
<your code>
```
````
