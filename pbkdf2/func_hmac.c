#include <openssl/hmac.h>
#include <openssl/sha.h>
#include <string.h>

typedef unsigned long size_t;

int KDF_PBKDF2_MIN_KEY_LEN_BITS = 112;
int KDF_PBKDF2_MAX_KEY_LEN_DIGEST_RATIO = 0xFFFFFFFF;
int KDF_PBKDF2_MIN_ITERATIONS = 1000;
int KDF_PBKDF2_MIN_SALT_LEN = 128 / 8;

int pbkdf2_derive(const char *pass, size_t passlen,
                         const unsigned char *salt, int saltlen, uint64_t iter,
                         const EVP_MD *digest, unsigned char *key,
                         size_t keylen, int lower_bound_checks)
{
    int ret = 0;
    unsigned char digtmp[EVP_MAX_MD_SIZE], *p, itmp[4];
    int cplen, k, tkeylen, mdlen;
    uint64_t j;
    unsigned long i = 1;
    HMAC_CTX *hctx_tpl = NULL, *hctx = NULL;

    mdlen = 20;

    /*
     * This check should always be done because keylen / mdlen >= (2^32 - 1)
     * results in an overflow of the loop counter 'i'.
     */
    if ((keylen / mdlen) >= KDF_PBKDF2_MAX_KEY_LEN_DIGEST_RATIO) {
        return 0;
    }

    if (lower_bound_checks) {
        if ((keylen * 8) < KDF_PBKDF2_MIN_KEY_LEN_BITS) {
            return 0;
        }
        if (saltlen < KDF_PBKDF2_MIN_SALT_LEN) {
            return 0;
        }
        if (iter < KDF_PBKDF2_MIN_ITERATIONS) {
            return 0;
        }
    }

    hctx_tpl = HMAC_CTX_new();
    p = key;
    tkeylen = keylen;
    HMAC_Init_ex(hctx_tpl, pass, passlen, digest, NULL);
    hctx = HMAC_CTX_new();

    while (tkeylen) {
        if (tkeylen > mdlen)
            cplen = mdlen;
        else
            cplen = tkeylen;

        //memset(digtmp, 0, sizeof(digtmp)); // digtmp is overridden in every loop

        /*
         * We are unlikely to ever use more than 256 blocks (5120 bits!) but
         * just in case...
         */
        itmp[0] = (unsigned char)((i >> 24) & 0xff);
        itmp[1] = (unsigned char)((i >> 16) & 0xff);
        itmp[2] = (unsigned char)((i >> 8) & 0xff);
        itmp[3] = (unsigned char)(i & 0xff);

        HMAC_CTX_copy(hctx, hctx_tpl);
        HMAC_Update(hctx, salt, saltlen);
        HMAC_Update(hctx, itmp, 4);
        HMAC_Final(hctx, digtmp, NULL);

        memcpy(p, digtmp, cplen);

        for (j = 1; j < iter; j++) {
            HMAC_CTX_copy(hctx, hctx_tpl);
            HMAC_Update(hctx, digtmp, mdlen);
            MAC_Final(hctx, digtmp, NULL);

            for (k = 0; k < cplen; k++)
                p[k] ^= digtmp[k];
        }
        tkeylen -= cplen;
        i++;
        p += cplen;
    }
    ret = 1;

    HMAC_CTX_free(hctx);
    HMAC_CTX_free(hctx_tpl);
    return ret;
}

int main(int argc, char** argv) {

    char pass[]="password";
    char salt[] = "salt";
    int iter=4096;
    int key_len = 20;
    char result[key_len];

    int success = pbkdf2_derive(pass, sizeof(pass)-1, salt, sizeof(salt)-1, iter, EVP_sha1(), result, key_len, 0);

    if (!success) {
        printf("error\n");
        return 1;
    }

    for (int i=0; i<key_len; i++) {
        printf("%hhx", result[i]);
    }
    printf("\n");

    return 0;
}