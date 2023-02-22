#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <papi.h>

int main(int argc, char *argv[])
{
  long n = atoi(argv[1]);
  long cplen = atoi(argv[2])*1000;

  char* data = "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";
  char* data_ls = malloc(sizeof(char) * cplen);
  memcpy(data_ls, data, 2000);
  char* str_cp = "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";
  char* p = malloc(sizeof(char)*n*cplen);
  memcpy(p, str_cp, 3500);
  long p_twin = 0;

  char* q = p;

  PAPI_hl_region_begin("computation");
  for (long i=0; i<n*cplen; i+=cplen) {
    for (long k=0; k<cplen; k++) {
      p[k + p_twin] ^= data_ls[k];
    }
    p_twin += cplen;
  }
  PAPI_hl_region_end("computation");

  char checksum = 0;
  for (int i=0; i<n*cplen; i++) {
    checksum ^= q[i];
  }
  printf("%x\n", checksum & 0xff);

  return 0;
}
