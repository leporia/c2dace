#include <openssl/evp.h>

int main(int argc, char *argv[])
{
  char pass[]="password";
  char salt[] = "salt";
  int iter=1048576;
  int key_length = 80;
  char result[key_length];
  int success = PKCS5_PBKDF2_HMAC(pass, sizeof(pass) -1, salt, sizeof(salt)-1, iter, EVP_sha1(), key_length , result);

  for (int i=0; i<key_length; i++) {
    printf("%hhx", result[i]);
  }
  printf("\n");
  return 0;
}