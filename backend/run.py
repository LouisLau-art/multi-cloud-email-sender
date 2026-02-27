import uvicorn
import os
import sys

if __name__ == "__main__":
    # 冻结环境（打包后）通常需要指定绝对路径，或者依赖 uvicorn 的自动发现
    # 这里我们直接启动
    # reload=False 因为打包后不需要热重载
    # workers=1 避免多进程打包复杂化
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False, workers=1)
