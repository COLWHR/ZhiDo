const config = require('./config')
const { request } = require('./request')

function buildSocketUrl(forumId, ticket) {
  const base = config.getWsBaseUrl()
  const query = ticket ? `?ticket=${encodeURIComponent(ticket)}` : ''
  return `${base}/forums/${forumId}/ws${query}`
}

function connectForumSocket(forumId, handlers) {
  let socketTask = null
  let closed = false

  // 小程序 wx.connectSocket 不能设置 Authorization 头，因此先换一个 2 分钟有效
  // 的一次性票据，避免把长效 access token 拼进 URL。
  const controller = {
    close() {
      closed = true
      if (socketTask) {
        try {
          socketTask.close()
        } catch (err) {
          // ignore
        }
        socketTask = null
      }
    },
    send(options) {
      if (!socketTask) return
      try {
        socketTask.send(options)
      } catch (err) {
        // ignore
      }
    },
  }

  request({ url: `/forums/${forumId}/ws-ticket`, method: 'POST' })
    .then((res) => {
      if (closed) return
      const ticket = res && res.data ? res.data.ticket : ''
      if (!ticket) {
        if (handlers && handlers.onError) handlers.onError({ errMsg: 'ws ticket missing' })
        return
      }

      socketTask = wx.connectSocket({ url: buildSocketUrl(forumId, ticket) })

      socketTask.onOpen((event) => {
        if (handlers && handlers.onOpen) handlers.onOpen(event)
      })

      socketTask.onClose((event) => {
        if (handlers && handlers.onClose) handlers.onClose(event)
      })

      socketTask.onError((event) => {
        if (handlers && handlers.onError) handlers.onError(event)
      })

      socketTask.onMessage((event) => {
        let data = event.data
        if (typeof data === 'string') {
          try {
            data = JSON.parse(data)
          } catch (err) {
            // keep raw string
          }
        }
        if (handlers && handlers.onMessage) handlers.onMessage(data, event)
      })
    })
    .catch((err) => {
      if (handlers && handlers.onError) handlers.onError(err)
    })

  return controller
}

module.exports = {
  buildSocketUrl,
  connectForumSocket,
}
