#include <openssl/hmac.h>
#include <string.h>
#include <omp.h>
//#include <papi.h>

/*
#define KDF_PBKDF2_MIN_KEY_LEN_BITS 112
#define KDF_PBKDF2_MAX_KEY_LEN_DIGEST_RATIO 0xFFFFFFFF
#define KDF_PBKDF2_MIN_ITERATIONS 1000
#define KDF_PBKDF2_MIN_SALT_LEN 128 / 8
*/

HMAC_CTX *hctx;
#pragma omp threadprivate(hctx)

int pbkdf2_derive(const char *pass, size_t passlen,
                         const unsigned char *salt, int saltlen, uint64_t iter, unsigned char *key,
                         size_t keylen, int lower_bound_checks)
{
    uint64_t KDF_PBKDF2_MIN_KEY_LEN_BITS = 112;
    uint64_t KDF_PBKDF2_MAX_KEY_LEN_DIGEST_RATIO = 0xFFFFFFFF;
    uint64_t KDF_PBKDF2_MIN_ITERATIONS = 1000;
    uint64_t KDF_PBKDF2_MIN_SALT_LEN = 128 / 8;

    int ret = 0;
    unsigned char *p;
    int tkeylen, mdlen;
    unsigned long i = 1;
    HMAC_CTX *hctx_tpl = 0;

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
    HMAC_Init_ex(hctx_tpl, pass, passlen, EVP_sha1(), 0);

    #pragma omp parallel
    {
        hctx = HMAC_CTX_new();
    }

    //PAPI_hl_region_begin("computation");
    #pragma omp parallel
    while (tkeylen) {
        unsigned char digtmp[EVP_MAX_MD_SIZE], itmp[4];
        unsigned char *local_p;
        int local_i, local_tkeylen;
        int cplen;

        #pragma omp critical
        {
            local_p = p;
            local_i = i;
            local_tkeylen = tkeylen;

            if (tkeylen > mdlen) {
                cplen = mdlen;
            } else {
                cplen = tkeylen;
            }

            tkeylen -= cplen;
            i++;
            p += cplen;
        }

        if (local_tkeylen <= 0) {
            break;
        }

        itmp[0] = (unsigned char)((local_i >> 24) & 0xff);
        itmp[1] = (unsigned char)((local_i >> 16) & 0xff);
        itmp[2] = (unsigned char)((local_i >> 8) & 0xff);
        itmp[3] = (unsigned char)(local_i & 0xff);

        HMAC_CTX_copy(hctx, hctx_tpl);
        HMAC_Update(hctx, salt, saltlen);
        HMAC_Update(hctx, itmp, 4);
        HMAC_Final(hctx, digtmp, 0);

        memcpy(local_p, digtmp, cplen);

        for (int j = 1; j < iter; j++) {
            HMAC_CTX_copy(hctx, hctx_tpl);
            HMAC_Update(hctx, digtmp, mdlen);
            HMAC_Final(hctx, digtmp, 0);

            for (int k = 0; k < cplen; k++)
                local_p[k] ^= digtmp[k];
        }
    }
   // PAPI_hl_region_end("computation");
    ret = 1;

    HMAC_CTX_free(hctx);
    HMAC_CTX_free(hctx_tpl);
    return ret;
}

int main(int argc, char** argv) {

    char *pass = "password";
    unsigned char *salt = "salt";
    int iter=10000000;
    long key_length = 80;
    unsigned char result[80];

    //int success = pbkdf2_derive(pass, sizeof(pass)-1, salt, sizeof(salt)-1, iter, result, sizeof(result)-1, 0);
    //omp_set_num_threads(4);
    int success = pbkdf2_derive(pass, 8, salt, 4, iter, result, key_length, 0);

    if (!success) {
        printf("error\n");
        return 1;
    }

    for (long i=0; i<key_length; i++) {
        printf("%hhx", result[i]);
    }
    printf("\n");

    return 0;
}
