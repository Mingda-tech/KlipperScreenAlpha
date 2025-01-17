### AI 打印质量监控系统设计方案（含JWT认证）

#### 1. 系统架构概述

为了实现高效、安全且易于维护的AI打印质量监控系统，我们将采用分层架构，其中KlipperScreen作为用户界面，Moonraker作为中间件处理打印机控制和与云服务的通信，而云服务负责AI分析。

#### 2. 功能模块设计

#### 2.1 用户界面 (KlipperScreen)
- **设置页面**：允许用户配置AI服务选项（如是否开启AI服务、是否开启AI云服务、置信度阈值、是否暂停等）。
- **实时监控**：显示摄像头预览、打印状态信息，并提供触发AI检测的功能。
- **结果展示**：接收并解析来自Moonraker的AI分析结果，根据设定规则决定是否弹出警告或暂停打印。
- **历史记录**：管理所有已完成任务的历史记录及对应的分析结果。

#### 2.2 中间件 (Moonraker)
- **API网关**：处理来自KlipperScreen的所有请求，包括图片上传、打印机控制命令等。
- **任务调度器**：定期触发图片采集和上传操作。
- **缓存管理**：存储临时图片文件，优化网络传输效率。
- **状态同步**：保持与Klipper的实时通信，确保UI界面上的状态信息准确无误。
- **认证管理**：通过JWT认证机制确保API请求的安全性。

#### 2.3 后端服务 (云服务)
- **AI分析平台**：接收图片并返回分析结果。
- **数据存储**：保存原始图片、分析结果及元数据。
- **认证授权**：保障设备和服务之间的安全通信。

### 3. 数据流向说明

1. **用户触发AI检测**
   - 用户在KlipperScreen上点击“AI检测”按钮。
   - KlipperScreen通过`/api/v1/camera/snapshot`接口向Moonraker发起请求，要求拍摄并上传图片。

2. **图片采集与上传**
   - Moonraker接收到请求后，协调摄像头资源，捕获图片并将其保存至本地缓存。
   - 图片随后被上传到云服务进行AI分析，使用`POST /api/v1/predict`接口发送图片URL及相关信息。

3. **接收AI分析结果**
   - 云服务完成图片分析后，将结果通过回调接口`POST /api/v1/ai/callback`返回给Moonraker。
   - Moonraker解析回调结果，并通过`/api/v1/ai/analysis/latest`接口将最新结果推送给KlipperScreen。

4. **根据结果采取行动**
   - KlipperScreen根据自身的AI设置判断是否需要进一步动作（如弹出警告或暂停打印）。
   - 如果需要暂停打印，KlipperScreen通过`/api/v1/printer/control`接口发送暂停命令给Moonraker。
   - Moonraker执行命令，并通过`/api/v1/printer/status`接口更新打印状态。

5. **实时状态更新**
   - KlipperScreen定期调用`/api/v1/printer/status`接口，以保持界面显示的状态与实际一致。

### 4. 接口文档

#### 4.1 图片采集接口
**目的**：从摄像头获取图片并上传至云服务进行AI分析。

- **URL**：`/api/v1/camera/snapshot`
- **方法**：`POST`
- **请求头**：
  - `Authorization: Bearer <JWT_TOKEN>`
- **请求参数**：
  - `camera_id` (string, 可选): 摄像头标识符，默认为主摄像头。
- **响应示例**：
  ```json
  {
    "status": "success",
    "message": "Image captured and uploaded successfully.",
    "image_url": "http://example.com/path/to/image.jpg"
  }
  ```

#### 4.2 调用AI服务接口
**目的**：上传图片至云服务进行AI分析。

- **URL**：`/api/v1/predict`
- **方法**：`POST`
- **请求头**：
  - `Authorization: Bearer <JWT_TOKEN>`
- **请求体**：
  ```json
  {
    "image_url": "http://example.com/images/xxx.jpg",
    "task_id": "PT202403120001",
    "callback_url": "http://cloud-service/api/v1/ai/callback"
  }
  ```
- **响应示例**：
  ```json
  {
    "status": "accepted",
    "message": "Analysis request received."
  }
  ```

#### 4.3 AI服务回调接口
**目的**：接收来自云服务的AI分析结果。

- **URL**：`/api/v1/ai/callback`
- **方法**：`POST`
- **请求体**：
  ```json
  {
    "task_id": "PT202403120001",
    "status": "success",
    "result": {
      "predict_model": "YOLO11",
      "has_defect": true,
      "defect_type": "stringing",
      "confidence": 0.95
    }
  }
  ```
- **响应示例**：
  ```json
  {
    "status": "success",
    "message": "Callback received and processed."
  }
  ```

#### 4.4 打印机控制接口
**目的**：发送控制命令给打印机，如暂停、恢复打印等。

- **URL**：`/api/v1/printer/control`
- **方法**：`POST`
- **请求头**：
  - `Authorization: Bearer <JWT_TOKEN>`
- **请求体**：
  ```json
  {
    "command": "pause" // 或者 "resume", "cancel"
  }
  ```
- **响应示例**：
  ```json
  {
    "status": "success",
    "message": "Command executed successfully."
  }
  ```

#### 4.5 打印状态查询接口
**目的**：实时获取打印机的工作状态。

- **URL**：`/api/v1/printer/status`
- **方法**：`GET`
- **请求头**：
  - `Authorization: Bearer <JWT_TOKEN>`
- **响应示例**：
  ```json
  {
    "status": "printing",
    "details": {
      "temperature": {
        "bed": 60,
        "tool0": 210
      },
      "progress": 75,
      "remaining_time": "01:30:00"
    }
  }
  ```

#### 4.6 AI 分析结果查询接口
**目的**：获取最近一次AI分析的结果。

- **URL**：`/api/v1/ai/analysis/latest`
- **方法**：`GET`
- **请求头**：
  - `Authorization: Bearer <JWT_TOKEN>`
- **响应示例**：
  ```json
  {
    "status": "success",
    "result": {
      "confidence": 0.85,
      "defects": [
        {"type": "overextrusion", "location": "bottom left"},
        {"type": "underextrusion", "location": "top right"}
      ]
    }
  }
  ```

### 5. 注意事项

- **错误处理**：对于每个API接口，都需要考虑可能出现的错误情况，并提供相应的错误码和描述信息。
- **安全性**：确保所有API请求都经过身份验证和授权，防止未授权访问。使用JWT令牌来保护API调用的安全性。
- **版本控制**：建议在URL中包含版本号（例如`/api/v1/camera/snapshot`），以便于管理不同版本间的兼容性。
- **性能优化**：考虑到3D打印过程中可能频繁调用API，应该对API进行性能优化，例如减少不必要的字段传输、使用缓存机制等。

### 6. 流程图

```plaintext
+------------------+       +------------------+       +------------------+
|                  |       |                  |       |                  |
|  KlipperScreen   | <---->|     Moonraker    | <---->|    Cloud Service |
|                  |       |                  |       |                  |
+------------------+       +------------------+       +------------------+
         ^                           ^                          ^
         |                           |                          |
         |                           |                          |
         v                           v                          v
+------------------+       +------------------+       +------------------+
|                  |       |                  |       |                  |
|  用户交互        |       |  图片上传 &      |       |  AI分析          |
|  和设置管理      |       |  打印机控制      |       |  和结果返回      |
|                  |       |                  |       |                  |
+------------------+       +------------------+       +------------------+
```

### 结论

通过上述设计，我们构建了一个清晰的数据流和接口体系，确保了各个组件之间高效、安全的通信。Moonraker作为中间件，不仅简化了开发流程，还增强了系统的可靠性和可扩展性。KlipperScreen专注于用户界面和交互逻辑，而Moonraker则负责打印机控制和与云服务的通信。这种设计使得整个系统更加模块化、易于维护，并为未来的功能扩展提供了良好的基础。如果有任何特定需求或需要调整的地方，请随时告知！