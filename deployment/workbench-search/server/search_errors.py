"""Public search failures that distinguish recovery from an empty result set."""


class SearchProviderError(ValueError):
    def __init__(self, code, message, *, provider, retryable=False, next_action='switch_source'):
        super().__init__(message)
        self.code, self.provider = code, provider
        self.retryable, self.next_action = retryable, next_action

    def result(self):
        return {'items':[], 'status':'unavailable', 'source':self.provider, 'message':str(self),
            'error':{'code':self.code, 'provider':self.provider, 'message':str(self),
                     'retryable':self.retryable, 'next_action':self.next_action}}
