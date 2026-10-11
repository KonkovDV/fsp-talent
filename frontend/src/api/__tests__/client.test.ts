import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'
import { beforeEach, describe, expect, it } from 'vitest'
import { useAuthStore } from '../../store/authStore'
import { api, apiError } from '../client'

function jwt(exp: number) {
  return `h.${btoa(JSON.stringify({ exp, sub: 'person-1' }))}.s`
}

function response(config: InternalAxiosRequestConfig, status: number, data: unknown): AxiosResponse {
  return { data, status, statusText: String(status), headers: {}, config, request: {} }
}

describe('обновление access-токена', () => {
  beforeEach(async () => {
    await new Promise(resolve => setTimeout(resolve, 0))
    useAuthStore.getState().logout()
    useAuthStore.getState().setAuth(jwt(Math.floor(Date.now() / 1000) + 3600), 'participant')
  })

  it('три параллельных 401 обновляют токен одним запросом', async () => {
    let refreshes = 0
    const fresh = jwt(Math.floor(Date.now() / 1000) + 7200)
    api.defaults.adapter = async config => {
      const url = config.url ?? ''
      if (url.includes('/auth/refresh')) {
        refreshes += 1
        await new Promise(resolve => setTimeout(resolve, 30))
        return response(config, 200, { access_token: fresh })
      }
      const header = config.headers?.Authorization ?? config.headers?.get?.('Authorization')
      if (!String(header).includes(fresh)) {
        const error = new AxiosError('unauthorized', '401', config, {}, response(config, 401, {}))
        throw error
      }
      return response(config, 200, { ok: true })
    }
    const answers = await Promise.all([
      api.get('/candidates/me'), api.get('/notifications'), api.get('/candidates/me/results'),
    ])
    expect(refreshes).toBe(1)
    expect(answers.map(item => item.status)).toEqual([200, 200, 200])
    expect(useAuthStore.getState().token).toBe(fresh)
  })

  it('отказ refresh выходит один раз', async () => {
    let exits = 0
    const stop = useAuthStore.subscribe(state => {
      if (!state.token && !state.userRole) exits += 1
    })
    api.defaults.adapter = async config => {
      const url = config.url ?? ''
      if (url.includes('/auth/refresh')) {
        throw new AxiosError('no', '401', config, {}, response(config, 401, {}))
      }
      throw new AxiosError('unauthorized', '401', config, {}, response(config, 401, {}))
    }
    await expect(Promise.all([
      api.get('/candidates/me').catch(error => error),
      api.get('/notifications').catch(error => error),
    ])).resolves.toHaveLength(2)
    expect(exits).toBe(1)
    stop()
  })
})


describe('apiError — русские тексты валидации', () => {
  function err(data: unknown) {
    return { response: { data } }
  }

  it('переводит типичные сообщения pydantic/422', () => {
    expect(apiError(err({ detail: [{ loc: ['body', 'limit'], msg: 'Input should be less than or equal to 50', type: 'less_than_equal' }] }), 'x'))
      .toBe('limit: Значение должно быть не больше 50')
    expect(apiError(err({ detail: [{ msg: 'Field required' }] }), 'x')).toBe('Обязательное поле')
    expect(apiError(err({ detail: 'Input should be a valid UUID, invalid character' }), 'x')).toBe('Некорректный идентификатор')
    expect(apiError(err({ detail: "Input should be 'reviewing', 'accepted' or 'rejected'" }), 'x'))
      .toBe("Допустимые значения: 'reviewing', 'accepted' или 'rejected'")
  })

  it('оставляет уже русское сообщение envelope', () => {
    expect(apiError(err({ error: { code: 'conflict', message: 'Уже есть такая запись' } }), 'x')).toBe('Уже есть такая запись')
  })
})
