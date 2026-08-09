“组件通信我主要用过两种。第一种是父传子，通过 props 传递数据，比如聊天页面把 thinking 状态和消息列表传给子组件；第二种是子传父，通过自定义事件 emit，把按钮点击、删除、重命名这类动作抛给父组件处理。插槽我了解它主要用于通用容器组件，让父组件把内容插到子组件内部预留的位置。”
“getter 是 Vuex 的概念，本质上是对全局 state 的派生结果，作用上类似计算属性。我的这个项目实际用的是 Pinia，不是 Vuex，在 Pinia 里更多是通过 computed 去实现类似 getter 的效果。”


======================================================================================================================================================================================


创建vue脚手架：vue create my-vue-project

1. v-if : 销毁渲染 , 占用资源
2. v-show : 对属性的设置, display: none 隐藏。只隐藏不销毁，销毁成本高，频繁操作切换的要用show
3. v-model : 双向绑定数据, 一般用于表单
4. v-bind: 可简写：，比如:title , 单向数据绑定
5. methods:用于封装逻辑代码，里面定义方法()，函数的封装
5. computed : 计算属性, 利用缓存的机制, 提高效率, 减少资源占用，使用的时候可以不用加括号 
const currentMessages = computed(
  () => state.messagesByConversation[state.currentConversationId] || []
);

6. 修饰符的作用: 对输入值的限制约束 , 按键响应 等等
7. v-for 遍历数据
8. v-text ，v-html：区别于 v-html显而易见可以解析 html标签元素

el属性:用于设置Vue的生效位置，只能在根组件中进行挂载、设置。内部的子组件是不需要el属性的


1. 响应式数据与插值表达式：
监听器：watch{}，监听的必须是响应式数据，里面监听一个新值和一个旧值 

内容指令：v-text=''  v-html=''
渲染指令：v-for、v-if、v-show
属性指令：比如<p :title="title">这是内容</p>
事件指令：button，<button v-on:click="output">按钮</button>，<button @click="output">按钮</button> 
表单指令: v-model可以实现双向数据绑定
修饰符：比如<input type="text" v-model.trim="inputValue">

组件在使用的时候就是一个html的格式，是一个单独的vue实例

二、组件的通信方式
1.父传子:通过 props 属性进行处理，父组件把数据传给子组件，子组件只负责接收和展示
2.子传父：子组件向父组件传递数据使用自定义事件，methods方法里面通过this.$emit()用于触发自定义事件,$emit(参数一是事件的名称'', 参数二是事件要传递的数据)
this.$emit() 是 Vue 2 里 Options API 很常见的写法。
你现在这个项目主要是 Vue 3 script setup，更常见的是：
defineEmits()
模板里直接 $emit(...)
或者先 const emit = defineEmits(...) 再 emit(...)

3.插槽 ：插槽是“父组件往子组件内部塞一段结构”。适合做通用容器组件，比如弹窗、卡片、布局组件。【“这个项目里组件通信主要还是以 props 和自定义事件为主，插槽我理解它更适合做通用容器组件，比如父组件把一段内容插到子组件预留的位置中。”】

1. 父传子
父组件传：
<ThinkingPanel
  :visible="thinkingVisible"
  :collapsed="thinkingCollapsed"
  :is-active="thinkingVisible"
  :status="activeThinkingStatus"
  :logs="activeThinkingLogs"
/>
子组件接收的 props，也就是父组件传进来的属性：
const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  status: {
    type: String,
    default: "",
  },
  logs: {
    type: Array,
    default: () => [],
  },
});

2. 子传父：自定义事件 emit，通过 $emit 或 emit() 往外发   【子组件按钮被点击 → 子组件 emit → 父组件监听这个事件 → 父组件去调用方法改状态】
子组件触发：
defineEmits(["toggle", "clear"]);
模板里：
<button class="thinking-action" type="button" @click="$emit('toggle')">
意思是：子组件点按钮时，触发一个叫 toggle 的事件。

父组件接收
<ThinkingPanel
  ...
  @toggle="$emit('toggle-thinking')"
  @clear="$emit('clear-thinking')"
/>
<MessageList
  ...
  @toggle-thinking="toggleThinkingCollapsed"
  @clear-thinking="clearLastThinking"
/>

3. props 一般是 properties 的简写，props 就是组件的属性。父组件通过 props 给子组件传值，子组件通过 props 接收外部传进来的数据
【“props 可以理解成组件对外暴露的参数，父组件把数据作为属性传给子组件，子组件再通过 props 接收并使用这些数据。”】

三、 vuex和router

getter属于Vuex的内容，它就是“对 state 做二次计算后的结果”，可以理解成“全局状态里的计算属性”
可以这么理解：state：原始数据； getter：基于原始数据算出来的新数据
state: {
  count: 1
},
getters: {
    //这个 doubleCount 就很像组件里的 computed
  doubleCount: (state) => state.count * 2
}

Vue Router 就是 Vue 项目的路由管理工具。
它负责：URL 和页面组件的对应关系/页面跳转/前端单页应用里的“切页不刷新”
先定义：/auth 对应登录页、/chat 对应聊天页、/documents 对应文档页
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/auth", name: "auth", component: AuthPage },
    { path: "/chat", name: "chat", component: ChatPage },
    { path: "/documents", name: "documents", component: DocumentsPage },
  ],
});
然后在组件里跳转：
router.push("/chat")
router.replace("/auth")
区别push：保留历史记录； replace：替换当前记录   【如登录成功后常用 replace("/chat")，这样用户点浏览器返回时不会又回到登录页】


Volar 是 Vue 3 官方主流的 VS Code 插件，主要作用是让你写 .vue 文件时更舒服。

四、reactive和ref的区别
reactive：通常用来处理 对象 / 数组，reactive 用来把一个对象变成响应式对象；访问属性时不用 .value ；写法更像普通对象操作
ref：通常用来处理 基本类型，也可以包对象 ；在 JS 里访问和修改通常要 .value ； 更适合单个值
const user = reactive({
  name: "Tom",
  age: 18,
})
const count = ref(0)
user.age++
count.value++

const user = ref({
  name: "Tom",
  age: 18,
})
user.value.age++

模板里为什么有时候不用 .value ？在 Vue 模板里，ref 会自动解包。
比如：
<template>
  <div>{{ count }}</div>
</template>
JS 里是：const count = ref(0)
模板里不用写 count.value，Vue 帮你自动处理了。
但在 script 里，通常还是要写 .value。

1.reactive
const user = reactive({
  name: "Tom",
  age: 18,
})
这时候 user.name、user.age 的变化，Vue 都能跟踪到。使用时也比较自然，直接写：user.age++

// 2. ref的使用:ref 要通过 .value 取值和改值
【因为基本类型本身不能像对象那样直接做响应式拦截，所以 ref 会在内部把这个值包装成一个带 value 属性的对象，再对这个对象做响应式处理。因此在 JS 里访问和修改 ref 数据时，通常都要写 .value】
对基本类型值做响应式处理的话，因为它本身是不支持这种对象化操作的，所以是无法实现的。
如果声明的是ref，那么会在内部创建一个新的空的对象，然后把你要使用的这个0这个值挂在这个对象的value属性上（也就是帮你创建了一个对象，值为0.然后再对这个对象进行响应式处理，因此修改数据也只能对这个响应式对象里面的value进行处理）
例子：
const count = ref(0)  //这里的 0 本身不是对象，Vue 没法直接给一个数字做对象属性拦截，所以 Vue 会把它包一层，变成类似：{ value: 0}
在 JS 里修改时要写：count.value++
function clickHandler() {
  count.value++
}

3.readonly:只读的响应式对象，适合用在只希望外部读取、不希望外部直接修改的数据场景
const myData = readonly({
    name:'wuyou
    age:18,
    friends:['韩梅梅'，'李雷']
}]

4. computed
computed 是计算属性，适合根据已有响应式数据派生出一个新值（适合做派生状态），而且有缓存特性，只有依赖变化时才会重新计算。在项目里会用它去计算当前会话标题、当前消息列表、天气展示文案这类展示层数据。”
【“computed 本质上就是基于已有响应式数据推导出一个新值，适合处理有返回结果的派生数据，比如字符串长度、过滤后的列表、拼接后的显示文案等。”】
它依赖某些响应式数据，当依赖的数据变化时，它会重新计算；如果依赖没变，它会直接复用上一次结果，不会重复执行
const content=ref('这是一段测试内容')
const getLen = computed(() => {
    console.log('计算属性执行了')
    return content.value.length
}   //只有 content.value 变化时，getLen 才会重新计算

5. watch：监听单一数据，监听器，适合在数据变化后执行某些动作，比如发请求、做联动或者打印日志
“监听某个响应式数据的变化，一旦变化，就执行指定逻辑。”
监听 ref：直接写变量名
监听 reactive 的某个属性：写成函数
监听整个 reactive 对象：直接写对象名

computed：更适合“算一个结果”   ；watch：更适合“数据变了以后去执行动作”。
针对我们不同形式对象的一个操作:①如果侦听的是ref对象本身不需要写value，直接写名称；如果侦听的是reactive的属性，需要通过一个函数的方式来做包裹，不能直接写属性本身；如果直接侦听reactive对象本身，直接写 myData就可以了

const count = ref(0)
watch(count,(newValue,oldValue)=>{
    console. log (newValue, oldValue)

}}

①watch 监听 ref：如果监听的是 ref，直接写变量名就行：
const count = ref(0)
watch(count, (newValue, oldValue) => {
  console.log(newValue, oldValue)
})
这里不用写 count.value。因为 watch 监听的是这个响应式源本身。

②watch 监听 reactive 里的某个属性：如果是 reactive 里的某一个属性，不能直接写 myData.age，而要写成函数：
const myData = reactive({    //myData里面存在很多属性，如果里面的数据都是响应式的，那也可以监听一个具体属性比如age
  name: "wuyou",
  age: 18,
  friends: ["韩梅梅", "李雷"],
})

watch(() => myData.age, (newValue, oldValue) => {    //不能直接写myData.age，必须写() => myData.age 函数形式。因为 watch 需要你明确告诉它：“你到底要追踪哪个值”。() => myData.age 就是在告诉 Vue：请监听这个返回值
  console.log(newValue, oldValue)
})

③watch 监听整个 reactive 对象
watch(myData, (newValue, oldValue) => {
  console.log(newValue, oldValue)
})
这样就是监听整个对象。对象里任意响应式属性变化，都会触发。
不过要注意，监听整个对象时：用得太多可能会比较重，一般更推荐监听你真正关心的具体字段

6. watchEffect：可以一次监听多个响应式数据。不用手动指定监听哪个变量，只要在函数里用到了哪些响应式数据，它就会自动监听这些数据。
“watch 是明确监听，watchEffect 是自动监听。”

watchEffect 的特点是：不需要手动指定监听谁、它会自动收集回调函数里用到的响应式数据、这些数据一变，它就重新执行
watchEffect(() => {
    console.log('count的值为:'+ count.value +',age的值为:+ myData.age)
})

watch 和 watchEffect 的区别
watch：要明确指定监听谁、能拿到 newValue 和 oldValue、更适合精确监听某个值
watchEffect：不用手动指定监听源、自动收集依赖、更适合快速写联动逻辑或副作用逻辑

7. nextTick：等 Vue 完成 DOM 更新以后再执行后续逻辑，适合做输入框聚焦、滚动到底部这类需要拿真实 DOM 的操作。
nextTick 的作用是：“等 Vue 把这一次数据更新对应的 DOM 渲染完成之后，再执行后面的逻辑。”
因为 Vue 更新页面不是你一改数据，DOM 就立刻同步改完，它通常会先收集更新，再统一渲染。所以有时候你改完数据马上去拿 DOM，可能拿到的还是旧的。这时候就用 nextTick
比如await nextTick()。意思就是：先等页面更新完成，再执行后面的代码

nextTick 用在我需要等 DOM 更新完成后再操作页面元素的场景。比如项目里我做会话重命名时，要先把输入框渲染出来，再自动聚焦，所以会先修改状态，再 await nextTick()，然后去调用输入框的 focus。”
async function startEdit() {
  editing.value = true
  draftTitle.value = props.item.title || ""
  await nextTick()
  editorRef.value?.focus()
  editorRef.value?.select()
}
这里的逻辑是：
先把 editing.value = true
页面才会切换出输入框
但是这个输入框不是立刻就在 DOM 里
所以要 await nextTick()
等输入框真正渲染出来，再去 focus() 和 select()


五、 Pinia（与vuex的区域）:本质上是一套全局状态管理机制。核心思想：把共享状态和相关逻辑集中管理
它和普通函数调用有一点相似，都是“把逻辑集中起来，别到处乱写”，但它解决的问题和普通函数不完全一样。
Pinia 主要解决的是：多个页面、多个组件要共享同一份数据、这些数据变化后，相关组件要自动更新、业务逻辑不想全塞在页面组件里
比如你这个项目里：当前登录用户、当前会话 id、会话列表、每个会话的消息、thinking 面板状态、设置项。这些都不适合散落在很多组件里，所以放到 Pinia store 里统一管理。

“Pinia 跟普通函数调用是不是一个思想？”
“有一点相似，都是把逻辑封装起来供外部调用，但 Pinia 不只是函数封装，它更重要的是提供了全局共享的响应式状态。普通函数更像工具方法，调用完就结束；Pinia store 则更像一个全局状态中心，里面既有共享数据，也有修改这些数据的方法，而且状态变化后页面会自动更新。”
如果他继续问 Pinia 和 Vuex，你可以接着说：
“Vuex 和 Pinia 都是状态管理工具。相比 Vuex，Pinia 写法更轻，更符合 Vue 3 组合式 API 风格，不需要单独写 mutation，所以我在项目里用 Pinia 来管理登录态、会话列表、消息流和 thinking 状态这些全局共享数据。”

比如你有个普通函数，谁需要就调用它：
function formatUserName(user) {
  return user.name + "-" + user.id
}

Pinia 也有点像：把状态和方法封装到 store 里，页面需要时就去调用 store 里的方法
比如你项目里的src/stores/assistant.js)：
export const useAssistantStore = defineStore("assistant", () => {
  const state = reactive({...})

  async function handleCreateConversation() {
    ...
  }

  async function handleSendMessage() {
    ...
  }

  return {
    state,
    handleCreateConversation,
    handleSendMessage,
  }
})
页面里再去用：
const store = useAssistantStore()
store.handleSendMessage()
这一点看起来确实有点像“调用一个封装好的函数模块”。

Pinai和普通函数最大的区别
Pinia 不只是函数集合，它还带着“响应式状态”。
普通函数调用一般是：传参数、返回结果、调完结束
但 Pinia 里面的状态是全局共享、响应式的。
也就是说，只要 store 里的数据变了，依赖它的页面会自动更新。
这就是它和普通函数最本质的区别。普通函数：更像“工具”。Pinia：更像“全局共享的响应式数据中心 + 业务方法集合”


Pinia 和 Vuex 的关系：Pinia 和 Vuex 都是 Vue 的状态管理工具。
你可以简单记成：
Vuex 是上一代主流方案。Pinia 是现在 Vue 3 更推荐的方案
Vuex 特点： 概念比较多：强制拆成state / getters / mutations / actions等，写法相对重一些，尤其以前 mutation 要单独写，比较繁琐
Pinia 特点：写法更轻，更符合 Vue 3 组合式 API 的风格，不需要专门强制区分一堆概念，TypeScript 支持也更友好、
现在这个项目里就是用 Pinia 来集中管理登录态、会话状态、消息状态和设置项。
我在项目里把 Pinia 当成一个全局状态中心来用，把会话、消息、用户、设置这些共享数据统一放进去，再把创建会话、发送消息、切换会话这些逻辑也收口到 store 里，避免每个页面和组件都自己维护一套状态。

六、JavaScript 数据类型：通常分成两大类
1. 基本数据类型：Number、String、Boolean、Undefined（容器默认值）、Null、Symbol、BigInt （ES6 之后还补充了 Symbol 和 BigInt）
2. 引用数据类型：Object   （而数组、函数、日期这些，本质上也都属于对象类型，比如Array、Function、Date、RegExp都可以归到引用类型里。）

3. undefined 是什么？表示“声明了，但是还没有赋值”。比如：
let a
console.log(a) // undefined
你说“默认值”这个方向是对的，但更准确一点可以说：“undefined 表示变量已声明但未赋值，或者对象中不存在的属性，函数没有显式返回值时默认也会返回 undefined。”

4. null 是什么？表示“我主动赋值为空”。
比如：let user = null
undefined：还没有值
null：有意地设为空

5. 为什么 typeof null 是 object： 这是 JS 的历史遗留问题。“typeof null 返回 object 是 JavaScript 早期设计留下来的历史问题，并不代表 null 真的是对象。”


七、 浅拷贝和深拷贝

浅拷贝只复制第一层属性，如果内部还有对象或数组，拷贝后还是共享同一个引用；深拷贝会递归复制所有层级，使新旧对象完全独立。

“浅拷贝只复制对象的第一层属性，如果属性值还是对象或数组，那么拷贝前后仍然共享同一块引用地址；深拷贝会递归复制对象的所有层级，使新旧对象完全独立。
常见浅拷贝有展开运算符和 Object.assign，常见深拷贝可以用 structuredClone，或者一些工具库方法。”

浅拷贝：只复制第一层 深拷贝：会递归复制所有层级

1. 浅拷贝是什么？
如果对象里有基本类型，复制后互不影响；
但如果对象里嵌套了对象或数组，拷贝后的内部引用还是同一个，所以会互相影响。

常见浅拷贝方式：Object.assign()、展开运算符 ...、数组的 slice()、concat()

例子：
const obj1 = {
  name: "Tom",
  info: {
    age: 18
  }
}
const obj2 = { ...obj1 }
obj2.name = "Jerry"
obj2.info.age = 20
console.log(obj1.name) // Tom
console.log(obj1.info.age) // 20
这里：
name 是第一层基本类型，不受影响
info 是对象，浅拷贝后还是同一个引用，所以改了会互相影响


浅拷贝
对象浅拷贝：
function shallowClone(obj) {
  const target = {}
  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      target[key] = obj[key]
    }
  }
  return target
}
数组浅拷贝也可以写：
function shallowCloneArray(arr) {
  return arr.slice()
}
更常见的简写你也要知道：
const newObj = { ...obj }
const newArr = [...arr]


2. 深拷贝是什么？
深拷贝会把对象里嵌套的对象、数组也一起复制出新的，不再共享引用。
比如：
const obj1 = {
  name: "Tom",
  info: {
    age: 18
  }
}
const obj2 = JSON.parse(JSON.stringify(obj1))
obj2.info.age = 20
console.log(obj1.info.age) // 18
这就是深拷贝。
不过要注意，JSON.parse(JSON.stringify()) 有局限：不能处理 undefined、不能处理函数、不能处理 Symbol、不能处理循环引用、Date 会变成字符串
如果环境支持的话，现在更推荐的是：
const newObj = structuredClone(oldObj)

深拷贝
最基础手写版：
function deepClone(obj) {
  if (obj === null || typeof obj !== "object") {
    return obj
  }

  const target = Array.isArray(obj) ? [] : {}

  for (const key in obj) {
    if (Object.prototype.hasOwnProperty.call(obj, key)) {
      target[key] = deepClone(obj[key])
    }
  }

  return target
}
这个版本适合笔试基础题。
如果题目问常见方法，也可以写：
const newObj = JSON.parse(JSON.stringify(obj))

“更完整的现代写法可以用 structuredClone()，但手写题里一般写递归版深拷贝更稳。


八、闭包： 函数和它能访问到的外部变量的组合。
闭包指的是函数可以记住并访问它定义时所在作用域中的变量，即使外层函数已经执行结束，这些变量仍然可以被内部函数访问。

“一个函数在外部作用域结束后，仍然能够记住并访问那个作用域里的变量，这种现象就叫闭包。”

“闭包本质上是函数和它所在词法作用域的组合。即使外层函数已经执行结束，内部函数仍然可以访问外层作用域中的变量。闭包常用于封装私有变量、保存状态以及实现函数工厂。”

例子：
function outer() {
  let count = 0
  function inner() {
    count++
    console.log(count)
  }

  return inner
}
const fn = outer()
fn() // 1
fn() // 2
fn() // 3

为什么这叫闭包？因为：outer() 执行完本来应该结束，但 inner() 还记住了 outer 里的 count，所以每次调用 fn()，都还能继续访问并修改 count，这就是闭包。
闭包常见作用：封装私有变量、保存状态、函数工厂、回调函数里访问外部变量
比如上面的 count，就像一个私有变量，外面不能直接改，只能通过 inner 来改。
闭包的注意点： 闭包不是坏东西，它很常用。但如果使用不当，可能会：占用内存，让一些本来该释放的变量一直保留下来


九、原型和原型链
原型是对象共享属性和方法的公共区域，原型链则是对象查找属性时沿着原型不断向上查找的过程。

1. 原型是什么：JavaScript 里很多对象在创建时，都会关联一个“原型对象”。如果当前对象本身没有某个属性或方法，就会去它的原型对象上找。

“原型可以理解为对象共享属性和方法的公共区域。当对象本身没有某个属性或方法时，会沿着它的原型去查找；如果原型上也没有，就继续沿着原型的原型往上找，这个查找过程就叫原型链。这样设计的好处是方法可以被多个实例共享，减少内存开销。”

比如：
const arr = [1, 2, 3]
你能写：arr.push(4)
但你自己并没有给 arr 定义 push。为什么能用？因为 push 在数组的原型对象上，也就是 Array.prototype 上。
所以原型可以理解成：“对象共享方法和属性的一块公共区域。”

2. 原型链是什么：如果一个对象自己没有这个属性，就去它的原型上找；
原型上还没有，就继续往原型的原型上找；这样一层一层往上找，就形成了原型链。
所以原型链本质上就是：“对象查找属性和方法时，沿着原型不断向上查找的链式过程。”
举个简单例子：const arr = [1, 2, 3]
查找 arr.toString() 时：先看 arr 自己有没有 toString，没有的话，去 Array.prototype 上找，还没有的话，再往上到 Object.prototype，再没有就到 null。这就是查找链路。
构造函数、prototype、proto这个是原型题很常见的点。

先记三句话：
每个构造函数都有一个 prototype
每个实例对象都有一个内部原型，通常可以通过 __proto__ 看到
实例对象的 __proto__ 指向构造函数的 prototype

例子：
function Person(name) {
  this.name = name
}
Person.prototype.sayHi = function () {
  console.log("hi")
}
const p1 = new Person("Tom")
关系是：Person.prototype：构造函数的原型对象
p1.__proto__ === Person.prototype：成立
所以 p1 可以调用：p1.sayHi()  。因为它会沿着原型链去 Person.prototype 上找。
为什么要有原型？ 因为这样可以节省内存。如果每创建一个对象都复制一遍相同的方法，会浪费资源。放到原型上，所有实例共享同一份方法就行。


十、防抖和节流

1. 防抖和节流的区别
防抖：事件结束后执行一次，认最后一次，适合搜索输入、表单校验 【比如搜索框输入：用防抖更合适,因为用户可能一直在打字，我们一般只想在他输入完成后查一次】
节流：事件持续触发时，按时间间隔执行，适合滚动、拖拽、鼠标移动 【比如滚动加载：用节流更合适,因为滚动过程中需要持续响应，但不能每次滚动都执行】

“防抖和节流都是为了优化高频事件。防抖指的是事件被频繁触发时，只在最后一次触发结束后一段时间再执行，适合搜索输入、表单校验这类场景；节流指的是在一段时间内无论触发多少次，都只执行一次，适合滚动、拖拽、鼠标移动这类持续触发的场景。防抖更强调‘只执行最后一次’，节流更强调‘按固定频率执行’。”
如果会话搜索、窗口 resize 或滚动加载这类交互变多，我会考虑加防抖或节流。比如搜索输入更适合防抖，避免每输入一个字都去做过滤或请求；而滚动监听更适合节流，避免高频触发影响页面性能。


2. 防抖：触发很多次，只在最后一次触发结束后一段时间再执行。  “防抖就是防止频繁触发，只认最后一次。”
连续触发事件，只要中间没有停下来，就一直重新计时，等你彻底停下来一小段时间后，才真正执行一次
最典型场景：搜索框输入，窗口 resize，表单校验
比如用户一直在输入搜索内容，如果每输入一个字都立刻发请求，会很浪费。
这时候就可以做防抖：“只有用户停止输入 500ms 后，才发一次请求。”

简单实现：
function debounce(fn, delay) {
  let timer = null                    // timer 用来保存定时器 id, 初始是 null，表示当前还没有定时任务
    // 返回一个新的函数, 以后真正绑定事件、被反复触发的，其实是这个返回的新函数
  return function (...args) {         // ...args 叫“剩余参数”：把调用这个函数时传进来的所有参数，收集成一个数组; 比如调用时写 debounceFn(1, 2, 3),那么 args 就是 [1, 2, 3]
    clearTimeout(timer)               // 每次触发时，先把上一次还没来得及执行的定时器清掉
    timer = setTimeout(() => {        // 重新开启一个新的定时器, delay 时间到了以后，才真正执行 fn
      fn.apply(this, args)            // apply(this, args) 的意思是：1. 用当前的 this 去调用 fn  2. 把 args 这个数组里的参数传给 fn
    }, delay)
  }
}

3. 节流：触发很多次，但规定一段时间内只执行一次。“节流就是稀释频率，按固定节奏执行。” 不管事件触发多频繁，到了规定时间间隔，才允许执行一次、  
典型场景：页面滚动 scroll、鼠标移动 mousemove、拖拽、高频点击控制
比如滚动事件会触发很多次，如果每次都执行复杂逻辑，页面会卡。
这时候可以节流：“每隔 200ms 最多执行一次。”
简单实现：
function throttle(fn, delay) {
  let lastTime = 0                       // lastTime 记录上一次真正执行 fn 的时间
  return function (...args) {            // 返回一个新的函数，这个函数会被高频触发 ,...args 同样表示：把本次调用传进来的所有参数收集成数组
    const now = Date.now()
    if (now - lastTime >= delay) {       // 如果当前时间和上一次执行时间的差值 >= delay，说明已经过了规定间隔，可以执行
      fn.apply(this, args)               // 执行真正的函数。fn：你真正想执行的函数； this：保持调用时原本的上下文； args：把参数原样传过去
      lastTime = now                     // 更新“上一次执行时间”
    }
  }
}

返回的是一个新的包装函数，所以需要先把参数收集起来，后面再通过 fn.apply(this, args) 把原本的参数和 this 继续传给真正要执行的函数。

...args 是 剩余参数语法。作用是：把传进来的多个参数，收集成一个数组。
function test(...args) {
  console.log(args)
}

test(10, 20, 30)   //输出[10, 20, 30]

十一、 localStorage / sessionStorage / cookie
“localStorage、sessionStorage 和 cookie 都可以用于浏览器端存储数据。
localStorage 持久化时间最长，关闭浏览器后仍然存在；sessionStorage 只在当前会话中有效，关闭标签页后会清除；
cookie 容量较小，但会自动携带到请求头中，常用于和服务端进行会话管理。
localStorage 和 sessionStorage 一般更适合前端本地缓存，cookie 更常用于登录态等服务端相关场景。”

1. localStorage
永久存储在浏览器本地、不主动清除就一直存在、关闭浏览器再打开也还在、大小一般约 5MB、只能存字符串
常见用途：登录信息缓存、页面设置缓存、前端本地状态持久化
比如：
localStorage.setItem("token", "123")
const token = localStorage.getItem("token")
localStorage.removeItem("token")

2. sessionStorage
也是浏览器本地存储,但生命周期是“当前页面会话”,关闭当前浏览器标签页或窗口后就没了.也只能存字符串
常见用途：临时页面状态、单次会话缓存数据
比如：sessionStorage.setItem("name", "Tom")

3. cookie
也是浏览器存储数据的一种方式，体积比较小，一般约 4KB，可以设置过期时间，会跟随 HTTP 请求一起发给服务器
常见用途：登录态、会话信息、服务端识别用户
比如：document.cookie = "username=Tom"

十二、事件冒泡
1. 事件冒泡指的是：一个元素触发事件后，这个事件会从当前元素一层一层向外层父元素传播。(先触发子元素，再触发父元素)
比如页面结构是：
<div id="parent">
  <button id="child">点击我</button>
</div>
如果你点击 button，事件执行顺序默认通常是：先触发 button 自己的点击事件,再触发它父元素 div 的点击事件,再继续往更外层传,这就叫 冒泡(从里往外冒)
例子：
const parent = document.getElementById("parent")
const child = document.getElementById("child")
parent.addEventListener("click", function () {
  console.log("parent 被点击了")
})
child.addEventListener("click", function () {
  console.log("child 被点击了")
})
点击 child 时，输出通常是： child 被点击了  parent 被点击了

2. 事件捕获
事件捕获和冒泡相反。它指的是：事件先从最外层往目标元素传播，最后才到真正被点击的元素（从外往里找）

默认情况下，我们平时写的事件监听大多数都是冒泡阶段。如果你想在捕获阶段监听，要在 addEventListener 里传第三个参数
例如：
parent.addEventListener("click", function () {
  console.log("parent 捕获")
}, true)         //这里 true 表示在捕获阶段监听

child.addEventListener("click", function () {
  console.log("child 捕获")
}, true)        //这里 true 表示在捕获阶段监听
如果点击 child，捕获阶段会先从外到内执行：parent 捕获  child 捕获

默认情况下,第三个参数不写时，一般就是在 冒泡阶段 触发：
addEventListener("click", fn)   //冒泡
阻止冒泡:如果你不想让事件继续往父元素传播，可以用：
event.stopPropagation()

例子：
parent.addEventListener("click", function () {
  console.log("parent")
})

child.addEventListener("click", function (event) {
  console.log("child")
  event.stopPropagation()       //因为冒泡被阻止
})
点击 child 后只会输出：child

3. 一个完整事件传播过程
完整来说，一个事件一般会经历三个阶段：
捕获阶段:从外层往目标元素走
目标阶段:到达真正触发事件的那个元素
冒泡阶段:从目标元素再往外层返回

例子：
const parent = document.getElementById("parent")
const child = document.getElementById("child")

parent.addEventListener("click", function () {
  console.log("parent 冒泡")
})

child.addEventListener("click", function () {
  console.log("child 冒泡")
})

parent.addEventListener("click", function () {
  console.log("parent 捕获")
}, true)

child.addEventListener("click", function () {
  console.log("child 捕获")
}, true)

点击 child 的大致顺序是：
parent 捕获
child 捕获
child 冒泡
parent 冒泡


十三、DOM
// 查询元素
var contents = document.querySelectorAll('#container p)   //获取所有匹配元素，返回 NodeList
var secondItem = document.querySelector('.item')   //只获取第一个匹配元素，用于获取单一元素

// 获取父级、子级、同级元素 
var block = document.querySelector('#block')
block.parentElement  // 父元素
block.children  // 子元素
block.firstElementChild
block.lastElementChild

// 同级元素
block.previousElementSibling
block.nextElementSibling

样式处理：
block.style.width = '80px'
block.style.backgroundColor = 'tomato'
block.className = 'changeStyle'    //className 会直接整体覆盖类名，classList 更灵活
block.classList.add('changeStyle')
block.classList.remove('changeStyle')
block.classList.toggle('changeStyle')

文本处理
block.textContent = '普通内容<span class="bold-text">加粗的文本</span>'
block.innerHTML ='普通内容<span class="bold-text">加粗的文本</span>'
事件处理
(1)会出现覆盖:同一个事件多次赋值会覆盖前面的处理函数
block.onclick=function(){
    alert()
}
（2）不会出现覆盖,可以绑定多个事件处理函数
block.addEventListener('click',function(){
    alert('')
})

定时器：
setTimeout(function () {
  console.log('surprise')
}, 2000)

setInterval(function () {
  console.log('surprise')
}, 2000)

箭头函数版：
setTimeout(() => {
  console.log('surprise')
}, 2000)

setInterval(() => {
  console.log('surprise')
}, 2000)

十四、ES6
1. 变量和常量：
let：定义变量，块级作用域，不能重复声明；用于可变变量
const：定义常量，声明时必须赋值，也有块级作用域；用于不希望被重新赋值的常量
var 并不是“去掉了”，而是 ES6 之后更推荐用 let 和 const
let age = 18
age = 20
const name = "xiaoxiao"
// name = "Tom" // 报错

2. 模板字符串：用反引号 ` ` 包裹，支持换行和变量插值
const name = "xiaoxiao"
const age = 18
console.log(`我的名字是${name}，今年${age}岁`)

3. 数组解构赋值：    从数组中按位置取值，简化变量赋值
const [a,b,c]=[1,2,3]   
console.log(a, b, c) // 1 2 3

4. 对象解构赋值： 
// username是同名属性，userAge是age的别名，...是收集剩余属性；在解构赋值里，剩余参数 ... 必须放最后；如果是在赋值符号后面来操作的话，代表的是一个普通的拓展运算符，位置可以随便放
const {username, age:userAge, gender, ...otherInfo}={
  username: "xiaoxiao",
  age: 18,
  gender: "male",
  school: "GZHU",
  pro: "2"
}
console.log(username, userAge, otherInfo)    // 输出： xiaoxiao 18 { school: 'GZHU', pro: '2' }

在 左边解构位置 写 ...otherInfo，表示“收集剩余项”
在 右边数组/对象展开时，... 才叫“展开运算符”

5. 拓展运算符
数组展开：
const arrl = [1,2,3]
const arr2 = [4, 5, 6]
const arr3 = [...arr1] //作用是把arr1数组中的每一项依次展开
const arr4 = [...arr1, ...arr2, 10, 20]

对象也可以展开：（对象是无序的 ）
const obj1 = { name: "Tom", age: 18 }
const obj2 = { ...obj1, gender: "male" }


6. 数组方法 Array.from()  ：把类数组对象或可迭代对象转成真正的数组
const str = "hello"
const arr = Array.from(str)
console.log(arr) // ['h', 'e', 'l', 'l', 'o']
也常用于：
const divs = document.querySelectorAll("div")
const divArr = Array.from(divs)

7. 对象的方法 Object.assign()
作用：对象浅拷贝、合并对象          "Object.assign() 常用于浅拷贝和对象合并，但如果对象内部还嵌套对象，它复制的仍然是引用。"
对象是一个引用类型，正常来说通过赋值方式是无法得到一个对象的副本的，而是得到一个相同的引用，属于同一个没有意义，
因此希望对对象进行拷贝的话，可以通过Object.assign()进行对象的浅拷贝
const objA = {
  name: "吴悠",
  age: 18
}
const objB = Object.assign({}, objA)
objB.name = "xiaoxiao"
console.log(objA, objB) //结果就是：{name:'吴悠', age:18} {name:'xiaoxiao', age:18} 
对象的合并
const objC={
    gender:"male"
}
const objD= Object.assign({}, objA, objC)  
console.log(objD)    //结果就是：{name:'吴悠', age:18, gender:'male'}

8. Class
class A {
    //构造方法
    constructor (name, age) {
        this.name = name
        this.age = age
    }
    //自定义方法
    introduce(){
        console.log(`我的名字是${this.name}，我的年龄是${this.age}`)
    }
}
const al= new A('悠',18)
console.log(al)   //{name:'吴悠',age:18}
a1.introduce()

继承
class B extends A {
    constructor (name, age, gender) {
        super(name, age)
        this.gender = gender
    }
    sayHello () {
        console.log("你好，我是" + this.name)
    }
}
const b1 = new B("小李", 19, "女")
console.log(b1)
b1.sayHello()
b1.introduce()

9. 箭头函数
//简写，可以不用写return
const getSum1= n => n+3
//完整写法,要写return
const getSum1= n => {
    return n+3
}

多个参数：
const getSum2 = (n1, n2) => n1 + n2
console.log(getSum2(10, 20))
剩余参数：
const getSum3 = (n1, n2, ...other) => {    ...other 叫 剩余参数必须写最后
  console.log(n1, n2, other)
}

getSum3(10, 20, 100, 200, 300) // 10 20 [100, 200, 300]

//可能还会传更多的参数，但是不确定，那就可以写成...other，表示用other取得了所有剩余的实参，这里的...other必须在形参的最后去写
//这个..other参数在箭头函数里面叫做REST参数，可以收集未被前面形参接收的参数，并且以数组的形式保存

10. Promise / async / await
“async/await 是 Promise 的语法糖，让异步代码更像同步写法。await 后面一般接 Promise，异常处理通常配合 try...catch 使用。”

//Async await
//步骤一：准备一个返回promise对象的函数
function asyncTask() {
  return new Promise((resolve, reject) => {
    const isSuccess = true
    if (isSuccess) {
      resolve("任务处理成功的结果")
    } else {
      reject("任务处理失败的结果")
    }
  })
}
//步骤二：为使用await的函数添加async
async function main() {
  try {
    const data = await asyncTask()  //调用异步函数
    console.log(data)
  } catch (error) {
    console.log(error)
  }
}
//然后需要执行一下main函数
main()  


main()
11. Proxy 代理
//Proxy是一个构造函数，是一个类
const obj = {
  name: "xiaoxiao",
  age: 18
}

//创建一个obj的代理（对象），给它设置一个配置项（对象），代理可以获取、修改obj内部对应的属性，也就是所有对p1的操作都会反馈给obj
//后续操作的时候是直接操作p1而不是obj。改obj本身没啥用
get 拦截读取, set 拦截修改, set 最好返回 true
“Proxy 可以理解成对目标对象的一层代理，读取、修改、删除等操作都可以被拦截并自定义处理。

const p1 = new Proxy(obj, {
  get(target, property) {          //访问obj的时候会触发这个get函数，target指向被访问或者修改的数据对象;property是属性名，receiver是当前使用的这个proxy实例，receiver可以省略
    return target[property]        //更规范、更推荐写
  },
  set(target, property, value) {
    target[property] = value
    return true                    //Proxy 里的 set 最好显式 return true
  }
})
console.log(p1.name)
p1.age = 20
console.log(obj.age) // 20

为代理的目标本来就是 obj，所以：target === obj, target[property] 和 obj[property] 在这里结果差不多
const p1= new Proxy(obj,{
    
    get(target, property){
        return obj[property]
    },
    set(target, property,value){
        obj[property]=value

    }
})


12. module 模块 
常见模块化方案:ES Module、CommonJS

ES Module：
export const name = "Tom"
export default function sayHi() {}
导入：
import sayHi, { name } from "./test.js"

CommonJS（Node.js 常见）：
module.exports = {
  name: "Tom"
}
导入：
const obj = require("./test.js")



### 原生ajax
const xhr = new XMLHttpRequest()
// 获取
xhr.open('GET','http://wuyou.com/common/get?ame=吴悠&age=18')
xhr.send()
xhr.onreadystatechange = function () {
    if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200){
        console.log(xhr.responseText)               //这一步返回的只是字符串
        console.log(JSON.parse(xhr.responseText))   //通过JSON.parse把字符串转换成json格式
    }
}

// 发，请求
xhr.open('POST','http://wuyou.com/common/post')    //这里请求地址就不需要加参数了比如?name=吴悠&age=18
发的数据类型是多种多样的，需要在发送给服务端的时候要告诉服务端，我发的内容是什么样的格式。因此需要在send之前添加一个请求头，也就是设置请求头，发送给服务端的时候告诉它一些额外的信息
xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded')   //告诉服务端，我发的请求参数格式。这里是名=值的格式
xhr.send('name=吴悠&age=18')                                         // post发送参数的位置，是在send里面书写。如果缺少上面那一步，那么到这一步是能发送成功的，但是还没法获取响应数据
xhr.onreadystatechange = function () {
    if (xhr.readyState === XMLHttpRequest.DONE && xhr.status === 200){
        console.log(xhr.responseText)               //这一步返回的只是字符串
        console.log(JSON.parse(xhr.responseText))   //通过JSON.parse把字符串转换成json格式
    }
}


### Axios 
需要先引入或者安装
Axios 是封装好的函数也是对象

1. get请求
axios.get('http://wuyou.com/common/get?ame=吴悠&age=18')

(async () => {
    const res = await axios.get('http://wuyou. com/common/get?n&me=吴悠&age=18')
    console.log(res.data)
})()

//也可以把参数单独去处理
(async () => {
    //get请求如果要把参数单独处理，必须有“params”
    const resGet = await axios.get('http://wuyou. com/common/get',{
        params:{
            name:'吴悠',
            age:18
        }
    })
    console. log(resGet.data)

    //post请求必须把参数单独处理，并且不需要有“params”
    const resPost = await axios.post('http://wuyou.com/common/post',{
        name:'吴悠',
        age:18
    })
    console. log(resPost.data)


})()


//axios还可以通过creat方法进行自定义的对象功能设置
(async()=>{
    //创建一个实例来接收一下，后面就可以通过这个实例进行请求发送
    const ins = axios.creat({
        baseURL:'http://wuyou.com/common',
    })

    const resGet = await ins.get('/get',{     //axios要变成ins
        params:{
            name:'吴悠',
            age:18
        }
    })
    console. log(resGet.data)

    const resPost = await ins.post('post',{
        name:'吴悠',
        age:18
    })
    console. log(resPost.data)

})


(async()=>{
    const ins = axios.creat({
        baseURL:'http://wuyou.com/common',
    })
    // axios里面可以创建拦截器，有两种
    //第一种：request请求拦截器
    // 配置了拦截器以后，只要发送请求都会经过拦截器的处理
    ins.interceptors.request.use(config=>{
        console.log('发送了请求')
        //处理完毕之后要正常发送请求，需要有return config
        return config
    })

    //第二种：response响应拦截器
    //在每一个请求在收到响应前，提前对响应内容做一个预处理，比如格式的处理等等
    ins.interceptors.response.use(res=>{
        return res  //处理完毕通过return 的方式把处理后的结果再由底部的功能接收
    })

    const resGet = await ins.get('/get',{     //axios要变成ins
        params:{
            name:'吴悠',
            age:18
        }
    })
    console. log(resGet.data)

    const resPost = await ins.post('post',{
        name:'吴悠',
        age:18
    })
    console. log(resPost.data)

})


### fetch
1. get
//默认是get请求,返回的值也是一个promise
fetch('http://wuyou.com/common/get?ame=吴悠&age=18')
    .then(res=>{             //res是一个普通的响应内容
        if(res.ok){
            return res.json()   //直接把响应数据解析成为json对象
        }

    })
    //后续还需要基于上面的数据继续处理，还可以继续.then，这是promise的特性
    .then(data=>{
        console.log(data)
    })

2.post
//post请求,参数二的地方需要传一些相应的配置项（get的时候也可以传的，上面的实例简化了）
fetch('http://wuyou.com/common/post',{
    method:'POST',
    headers:{
        'Content-Type':'application/json'    //请求的参数的格式
    },
    //数据需要通过body来写
    //下面这样子写还只是一个传统的js对象，但是前面已经定义请求头为json，因此下面这样子写会报错
    body:{   
        name:'吴悠' ,
        age:18

    }
    //需要把js对象转为json对象，可以通过原生js的方法
    //JSON.stringify将js对象转成一个符合json格式的字符串，再通过请求发送走（JSON.stringify和JSON.parse是相互转换的）
    body:JSON.stringify{   
        name:'吴悠' ,
        age:18

    }

})
    .then(res=>{             //res是一个普通的响应内容
        if(res.ok){
            return res.json()   //直接把响应数据解析成为json对象
        }

    })
    //后续还需要基于上面的数据继续处理，还可以继续.then，这是promise的特性
    .then(data=>{
        console.log(data)
    })