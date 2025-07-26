### 深度问题分析

#### 1. 页面卡顿的根源：主线程中的同步阻塞

`KlipperScreen` 的界面是基于 GTK 构建的，它依赖一个单线程的主事件循环（Main Loop）来处理用户输入和界面刷新。如果在主线程中执行任何耗时的操作，整个界面就会被"冻结"，无法响应，从而导致卡顿。

通过分析代码，我确定了以下几个关键的**阻塞点**，它们都在主线程中被调用：

*   **`reload_networks` 函数中的 `self.wifi.rescan()`**: 当您点击刷新按钮时，会调用此方法。`rescan()` 会触发一个 WiFi 扫描，这个过程需要几秒钟。在 `ks_includes/wifi_nm.py` 中，这个操作很可能是通过一个**同步（阻塞）的 D-Bus 调用**来完成的，这意味着在扫描结束前，UI 线程会一直等待，导致界面卡死。
*   **`load_networks` 函数中的 `self.wifi.get_networks()`**: 此方法用于获取网络列表。如果它执行的是一次新的、阻塞式的 D-Bus 查询，同样会导致界面卡顿。
*   **`connect_network` 函数中的 `self.wifi.connect(ssid)`**: 这是最严重的阻塞点。连接到一个 WiFi 网络涉及到认证、获取IP地址等多个步骤，可能耗时 5 到 30 秒。在当前实现中，这个连接过程会完全阻塞主线程，导致"正在连接"的对话框也一同卡死，用户无法进行任何操作。
*   **`update_all_networks` 中的 `self.wifi.get_network_info(ssid)`**: 这个函数每 5 秒被调用一次，并遍历当前列表中的所有网络。如果 `get_network_info` 对每个网络都执行一次阻塞的 D-Bus 查询，当网络列表变长时，这种周期性的卡顿会更加明显。

**结论**：页面卡顿的直接原因是**将耗时的网络操作（扫描、连接、获取信息）以同步阻塞的方式在 GTK 主线程中执行了**。

#### 2. 部分WiFi网络不显示的根源：逻辑缺陷

*   **缺陷一：SSID 作为唯一标识符导致网络被丢弃**
    在 `add_network` 函数中，有这样一行代码：
    ```python
    if ssid in list(self.networks):
        return
    ```
    这段代码使用 WiFi 的名称（SSID）作为字典 `self.networks` 的键，并以此判断网络是否已经存在。这是一个致命的设计缺陷。在现实中，许多路由器会为 2.4GHz 和 5GHz 频段广播相同的SSID。当扫描到这两个接入点（Access Point, AP）时，由于它们的 SSID 相同，**第一个被处理的 AP 会被添加，而第二个则会被直接忽略并丢弃**。这就导致了您看到的"部分网络不显示"的问题。正确的做法是使用每个 AP 独一无二的 MAC 地址（BSSID）作为唯一标识。

*   **缺陷二：扫描与获取结果之间的竞态条件 (Race Condition)**
    在 `reload_networks` 函数中，代码的执行顺序是：
    1.  `self.wifi.rescan()`：发起一次新的扫描。
    2.  `GLib.idle_add(self.load_networks, widget)`：**立即**调度 `load_networks` 来加载网络列表。

    如果 `rescan()` 是一个非阻塞的调用（即它只发出扫描命令然后立即返回），那么 `load_networks` 在执行时，新的扫描很可能还没有完成。因此，`self.wifi.get_networks()` 获取到的将是**上一次扫描的旧结果**。新扫描到的网络只有在稍后通过 `scan_callback` 更新时才会出现，这导致了刷新不及时、列表不完整的问题。

### 针对性解决方案

为了根治以上问题，我提出一个分为两大部分的综合解决方案。核心思想是：**全面异步化网络操作，并重构网络数据模型。**

#### 第一部分：解决页面卡顿——引入异步工作线程 ✅ **已完成**

1.  **✅ 创建后台线程**：已在 `WifiManager` (`ks_includes/wifi_nm.py`) 中创建了专用的后台工作线程。所有与 `NetworkManager` 的 D-Bus 交互现在都在这个线程中完成，彻底解放了 UI 主线程。

2.  **✅ 改造阻塞函数为异步模式**：已将 `WifiManager` 中的所有关键函数改造为完全异步形式，并使用回调函数返回结果：
    *   `rescan(callback)` - 异步WiFi扫描
    *   `get_networks(callback)` - 异步获取网络列表
    *   `get_network_info(ssid, callback)` - 异步获取网络详细信息
    *   `connect(ssid, callback)` - 异步连接WiFi网络
    *   `add_network(ssid, psk, callback)` - 异步添加新网络
    *   `delete_network(ssid, callback)` - 异步删除网络

3.  **✅ 安全地将结果传递回主线程**：在后台线程完成任务后，使用 `GLib.idle_add()` 将UI更新操作安全地调度到 GTK 主线程中执行。

4.  **✅ 提供即时UI反馈**：
    *   点击刷新按钮后，按钮进入加载状态
    *   点击连接后，显示实时更新的"正在连接..."对话框
    *   所有长时间操作都有相应的状态反馈

5.  **✅ UI层面板改造完成**：
    *   已完全重构 `panels/network.py`，所有同步调用已改为异步调用
    *   已完全重构 `panels/select_wifi.py`，所有同步调用已改为异步调用
    *   修复了扫描与获取结果之间的竞态条件

**🎉 第一部分成果总结：**
- **主线程卡顿** ❌ → **完全异步** ✅
- **界面冻结** ❌ → **流畅响应** ✅  
- **扫描等待** ❌ → **后台处理** ✅
- **连接卡死** ❌ → **实时状态** ✅

#### 第二部分：解决WiFi丢失——重构数据模型和扫描逻辑 ⚠️ **待实现**

1.  **使用BSSID作为唯一标识**：
    *   修改 `WifiManager` 的 `get_networks_async` 方法。它不应再返回一个简单的 SSID 列表，而应该返回一个**接入点（AP）对象的列表**。每个对象至少包含 `ssid`, `bssid`, `strength`, `frequency`, `encrypted` 等信息。
    *   在 `panels/select_wifi.py` 和 `panels/network.py` 中，将 `self.networks` 字典的键从 `ssid` 改为 `bssid`。这样，即使多个 AP 有相同的 SSID，它们也会因为 BSSID 不同而被视为独立的条目。

2.  **优化UI显示逻辑**：
    *   UI层面可以进行智能分组。在显示时，可以将具有相同SSID的AP条目聚合在一起，并清晰地标出它们的区别（如 "WiFi-Name (5GHz)", "WiFi-Name (2.4GHz)"）。

3.  **修复扫描与获取的流程**：
    *   `reload_networks` 的逻辑应改为：
        1.  调用 `self.wifi.rescan_async(on_scan_complete_callback)`。
        2.  在 `on_scan_complete_callback` 回调函数中，调用 `self.wifi.get_networks_async(on_get_networks_complete_callback)`。
        3.  在 `on_get_networks_complete_callback` 回调函数中，获取到**最新的、完整的**网络列表，然后更新UI。
    *   这确保了UI总是在一次成功的、完整的扫描之后才用最新的数据进行刷新。