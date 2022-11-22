struct thread_initializer {
    explicit thread_initializer() {}

    thread_initializer(thread_initializer& _it) {
        hctx = HMAC_CTX_new();
    }

    struct hmac_ctx_st* hctx;
};