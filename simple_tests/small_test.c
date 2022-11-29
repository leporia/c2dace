int main(int argc, char** argv) {
    unsigned char itmp[1];

    int i = 0;
    int result = 0;

    for (int j=0; j<10; j++) {
        i = j;
        itmp[0] = (unsigned char)((i >> 24) & 0xff);
        result = itmp[0];
    }

    return result;
}